# validador_0200.py (v1.9.9)
r"""
Validador ISO 8583 para 0200/0400 e fallback 96x0/9610, com extração do Bit 47 (TLV) e seleção de cenário por roteiro.

- TLV flexível (LLL/LL)
- Âncoras específicas por pcode no 96x0
- Saída RAW (em --debug) com IDs/VLs do 47 sem whitelist
- Correções robustas:
    * MTI com header opcional (\d{6}) e leitura de bitmap prim/seg inline/linha (ignora whitespace);
    * secundário truncado -> limpa bit 1 e avança cursor (evita desalinhamento);
    * parser de campos parametrizável por FIELD_SPEC ativo (do roteiro/cenário/MTI);
    * DE90 lido apenas no 0400 (ou quando o cenário exigir);
    * bits >64 exigidos viram AVISO quando não houver secundário válido (não reprova).
"""

import json
import os
import re
import sys
from typing import Any, Dict, List, Set, Tuple, Optional

ROTEIRO_PATH = "roteiro_iso_0200.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOGS_DIR = os.path.join(BASE_DIR, "LOGS de TESTE")

#region Carregamento do roteiro

def load_roteiro(path=ROTEIRO_PATH) -> dict:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

#endregion

#region Bitmap (hex)

def hex_nibble_to_bits(h: str) -> List[int]:
    # Retorna os 4 bits do nibble em ordem MSB->LSB como ints [0/1]
    return [int(b) for b in bin(int(h, 16))[2:].zfill(4)]


def bitmap_hex_to_setbits(hex_str: str, base_index: int = 1) -> Set[int]:
    """
    Converte um bitmap em HEX (16 chars) para um conjunto de posições de bits ativas.
    base_index:
      - 1   -> bits 1..64 (primário)
      - 65  -> bits 65..128 (secundário)
    """
    bits_set: Set[int] = set()
    pos = 0
    for ch in hex_str:
        for bit in hex_nibble_to_bits(ch):
            pos += 1
            if bit == 1:
                bits_set.add(base_index + pos - 1)
    return bits_set

#endregion

#region Helpers de leitura de HEX

_HEXSET = set("0123456789ABCDEF")

def _strip_nonhex(text: str) -> str:
    """Remove tudo que não for [0-9A-F] e retorna uppercase."""
    return "".join(ch for ch in text.upper() if ch in _HEXSET)

def _read_hex16_from_next_nonempty_line(s: str, start_pos: int) -> Tuple[Optional[str], int]:
    """
    A partir de start_pos, encontra a próxima linha não vazia.
    Monta 16 hex a partir dessa linha (ignorando espaços/tabs).
    Retorna (hex16, new_pos_after_line) ou (None, start_pos) se falhar.
    """
    n = len(s)
    pos = start_pos

    while pos < n and s[pos] in "\r\n \t":
        pos += 1

    line_end = s.find("\n", pos)
    if line_end == -1:
        line_end = n

    line = s[pos:line_end]
    hex_only = _strip_nonhex(line)
    if len(hex_only) < 16:
        return None, start_pos

    hex16 = hex_only[:16]
    return hex16, line_end + 1

def _read_hexN_inline_relaxed(s: str, start: int, need: int = 16) -> Tuple[Optional[str], int, int]:
    """
    Lê até 'need' hex a partir de 'start', ignorando whitespace inline.
    Para se encontrar caractere não-hex (que não seja whitespace) antes de completar, para.
    Retorna (hex_str|None, new_pos, consumed_len):
      - hex_str quando conseguiu 'need' hex;
      - None quando não alcançou 'need' hex (consumed_len pode ser >0).
    """
    n = len(s)
    pos = start
    buf = []
    consumed = 0

    while pos < n and len(buf) < need:
        ch = s[pos]
        if ch.isspace():
            pos += 1
            continue
        up = ch.upper()
        if up in _HEXSET:
            buf.append(up)
            pos += 1
            consumed += 1
        else:
            break

    if len(buf) == need:
        return "".join(buf), pos, consumed

    return None, pos, consumed

#endregion

#region TLV do Bit 47

def parse_tlv_sequence(s: str, start: int, max_len: int = 20000) -> Tuple[Dict[str, str], List[str], int]:
    """
    Parser TLV ASCII flexível (no buffer global):
      - TAG: 3 dígitos ASCII (ex.: '001', '023', '046', etc.)
      - LEN: tenta primeiro LLL (3 dígitos). Se falhar, tenta LL (2 dígitos).
      - VAL: L bytes ASCII

    Retorna: (mapa {TAG:VAL}, ordem_dos_TAGs, pos_final)
    """
    n = len(s)
    pos = start
    end_limit = min(n, start + max_len)
    found_map: Dict[str, str] = {}
    order: List[str] = []

    while pos + 5 <= end_limit:
        id_ = s[pos:pos+3]
        if not id_.isdigit():
            break
        pos_len = pos + 3

        # Tenta LLL
        if pos_len + 3 <= end_limit and s[pos_len:pos_len+3].isdigit():
            L = int(s[pos_len:pos_len+3])
            pos_val = pos_len + 3
        # Se não deu LLL, tenta LL
        elif pos_len + 2 <= end_limit and s[pos_len:pos_len+2].isdigit():
            L = int(s[pos_len:pos_len+2])
            pos_val = pos_len + 2
        else:
            break

        if L < 0:
            break
        end_val = pos_val + L
        if end_val > end_limit:
            break

        val = s[pos_val:end_val]
        if id_ not in found_map:
            order.append(id_)
            found_map[id_] = val
        else:
            found_map[id_] += val

        pos = end_val

    return found_map, order, pos

# ========= Helpers para TLV dentro do DE47 (payload local) ==========

def parse_tlv_payload(payload: str) -> Tuple[Dict[str, str], List[str]]:
    """
    Lê TLV ASCII dentro de um payload (sem depender do buffer global):
      - TAG: 3 dígitos ASCII
      - LEN: tenta LLL(3) e, se falhar, LL(2)
      - VAL: L bytes ASCII
    Para quando não encontra próximo TAG numérico.
    """
    s = payload
    n = len(s)
    pos = 0
    found_map: Dict[str, str] = {}
    order: List[str] = []

    while pos + 5 <= n:
        id_ = s[pos:pos+3]
        if not id_.isdigit():
            break
        pos_len = pos + 3
        if pos_len + 3 <= n and s[pos_len:pos_len+3].isdigit():
            L = int(s[pos_len:pos_len+3])
            pos_val = pos_len + 3
        elif pos_len + 2 <= n and s[pos_len:pos_len+2].isdigit():
            L = int(s[pos_len:pos_len+2])
            pos_val = pos_len + 2
        else:
            break
        if L < 0 or pos_val + L > n:
            break
        val = s[pos_val:pos_val+L]
        if id_ not in found_map:
            order.append(id_)
            found_map[id_] = val
        else:
            found_map[id_] += val
        pos = pos_val + L

    return found_map, order

#endregion

#region ID 238 (sub-TLV)

class ID238Error(Exception):
    pass


def parse_id238_subtlv_ascii(payload: str, tag_width: int = 2, len_digits: int = 2) -> Dict[str, str]:
    """
    Lê sequência: TT(2) + LL(2 decimais) + valor(LL) ... até o fim do payload.
    Retorna dict {"00": "valor...", "01": "valor...", ...}
    Levanta ID238Error em caso de truncamento/length inválido.
    """
    s = payload
    n = len(s)
    i = 0
    out: Dict[str, str] = {}

    def read_len_decimal2(idx: int) -> int:
        if idx + 2 > n or not s[idx:idx+2].isdigit():
            raise ID238Error("Comprimento LL inválido em ID238 (esperado 2 dígitos decimais).")
        return int(s[idx:idx+2])

    if len_digits != 2:
        raise ID238Error(f"len_digits={len_digits} não suportado (use 2).")

    while i < n:
        if i + tag_width > n:
            raise ID238Error("Tag (TT) truncada no fim do ID238.")
        tag = s[i:i+tag_width]; i += tag_width

        if i + len_digits > n:
            raise ID238Error(f"Campo de comprimento (LL) truncado para TAG {tag}.")
        L = read_len_decimal2(i); i += len_digits

        if i + L > n:
            raise ID238Error(f"Valor da TAG {tag} truncado: LL={L}, faltam {i+L-n} chars.")
        val = s[i:i+L]; i += L

        out[tag] = val

    return out


def _is_ans(text: str) -> bool:
    # 'ans' ~ ASCII imprimível
    return all(32 <= ord(ch) <= 126 for ch in text)


def validate_id238_subtlv(subtags: Dict[str, str], id238_cfg: dict, txn_type: Optional[str] = None) -> List[str]:
    """
    Valida as sub-TAGs do 238 conforme JSON.
    """
    errors: List[str] = []

    # 1) Presença condicional por tipo de transação (opcional)
    req_by_txn = id238_cfg.get("required_tags", {})
    if txn_type and txn_type in req_by_txn:
        required = set(req_by_txn[txn_type])
        missing = required - set(subtags.keys())
        for t in sorted(missing):
            errors.append(f"DE47/ID238: sub-TAG obrigatória ausente no tipo '{txn_type}': {t}")

    # 2) Regras de conteúdo por TAG
    tags_spec: Dict[str, dict] = id238_cfg.get("tags", {})
    for t, val in subtags.items():
        rule = tags_spec.get(t)
        if not rule:
            continue

        name = rule.get("name", t)
        charset = rule.get("charset", "ans")
        exact = rule.get("exact_len")
        min_len = int(rule.get("min", 0))
        max_len = int(rule.get("max", 9999))
        L = len(val)

        # charset
        if charset == "numeric":
            if not val.isdigit():
                errors.append(f"DE47/ID238 {t} ({name}): esperado numérico, recebido '{val}'")
        elif charset == "ans":
            if not _is_ans(val):
                errors.append(f"DE47/ID238 {t} ({name}): caracteres não-ANS")

        # tamanho
        if exact is not None:
            if L != int(exact):
                errors.append(f"DE47/ID238 {t} ({name}): tamanho {L} != {exact} (exato)")
        else:
            if L < min_len or L > max_len:
                errors.append(f"DE47/ID238 {t} ({name}): tamanho {L} fora de [{min_len},{max_len}]")

    return errors


def validate_id238_if_present(
    bit47_map: Dict[str, str],
    profile: dict,
    amostras_bits: Dict[str, str],
    scenario: Optional[dict],
    errors_sink: List[str],
    debug: bool = False
) -> Optional[Dict[str, str]]:
    """
    Se ID 238 estiver presente no bit 47, parseia o sub-TLV e valida conforme profile.
    """
    id238_cfg = profile.get("de47_id238", {})
    if not id238_cfg:
        return None

    if "238" not in bit47_map:
        return None

    payload_238 = bit47_map["238"]
    subtags_238: Optional[Dict[str, str]] = None

    # 1) Parse do sub-TLV do 238
    try:
        tag_width = int(id238_cfg.get("subtlv", {}).get("tag_width", 2))
        len_fmt = id238_cfg.get("subtlv", {}).get("len_format", "decimal2")
        if len_fmt != "decimal2":
            errors_sink.append(f"DE47/ID238: len_format '{len_fmt}' não suportado (esperado 'decimal2').")
            return None
        subtags_238 = parse_id238_subtlv_ascii(payload_238, tag_width=tag_width, len_digits=2)
    except ID238Error as e:
        errors_sink.append(f"DE47/ID238: erro de parsing: {e}")
        return None

    # 2) Validar conteúdo conforme JSON + (opcional) txn_type_map via DE3
    txn_type = None
    txn_map = id238_cfg.get("txn_type_map", {})
    if txn_map:
        src_de = int(txn_map.get("source_field", 3))
        de_val = amostras_bits.get(f"{src_de:02d}") or amostras_bits.get(str(src_de))
        if de_val is not None:
            for label, accepted in txn_map.get("values", {}).items():
                if de_val in accepted:
                    txn_type = label
                    break

    errors_sink += validate_id238_subtlv(subtags_238, id238_cfg, txn_type=txn_type)

    # 3) Required do cenário (opcional)
    if scenario:
        req_238 = scenario.get("required_id238_tags", [])
        if req_238:
            missing = set(req_238) - set(subtags_238.keys())
            for t in sorted(missing):
                errors_sink.append(
                    f"Scenario {scenario.get('name')}: DE47/ID238 sub-TAG obrigatória ausente: {t}"
                )

    if debug:
        print("[DEBUG] ID238 subtags:", subtags_238)

    return subtags_238


def validate_bit47_id_rules(bit47_map: Dict[str, str], id_rules: Dict[str, dict]) -> List[str]:
    errors: List[str] = []
    if not id_rules:
        return errors

    for sid, rule in id_rules.items():
        if sid not in bit47_map:
            continue

        val = bit47_map.get(sid, "")
        charset = (rule.get("charset") or "").lower()
        exact_len = rule.get("exact_len")
        min_len = rule.get("min")
        max_len = rule.get("max")

        if charset == "numeric" and not val.isdigit():
            errors.append(f"Bit 47/ID {sid}: esperado numérico, recebido '{val}'")

        if exact_len is not None:
            if len(val) != int(exact_len):
                errors.append(f"Bit 47/ID {sid}: tamanho {len(val)} != {int(exact_len)} (exato)")
        else:
            if min_len is not None and len(val) < int(min_len):
                errors.append(f"Bit 47/ID {sid}: tamanho {len(val)} < {int(min_len)}")
            if max_len is not None and len(val) > int(max_len):
                errors.append(f"Bit 47/ID {sid}: tamanho {len(val)} > {int(max_len)}")

    return errors

#endregion

#region Finders de Bit 47 (fallback)

def find_best_bit47_sequence(
    raw: str,
    after_idx: int,
    allowed_ids: Set[str],
    required_ids: Set[str],
    debug: bool = False
):
    s = raw
    diag: List[dict] = []
    candidates = []
    for m in re.finditer(r'(?<!\d)001(?=\d{2,3})', s):
        start = m.start()
        if start < after_idx:
            continue
        mapp, order, endpos = parse_tlv_sequence(s, start)
        if not order:
            continue
        allowed_present = [i for i in order if i in allowed_ids] if allowed_ids else order[:]
        required_present = [i for i in set(mapp.keys()) if i in required_ids] if required_ids else []
        has_041 = "041" in mapp
        has_042 = "042" in mapp
        score = 5 * len(required_present) + 2 * (1 if has_041 else 0) + 2 * (1 if has_042 else 0) + len(allowed_present)
        candidates.append((mapp, order, start, endpos, score, {
            "start": start,
            "end": endpos,
            "total_ids": len(order),
            "allowed_present": allowed_present,
            "required_present": sorted(required_present),
            "score": score
        }))
    if not candidates:
        return {}, [], -1, -1, 0, diag
    candidates.sort(key=lambda x: (x[4], len(x[1]), x[3] - x[2]), reverse=True)
    best = candidates[0]
    if debug:
        diag = [c[5] for c in candidates]
    return best[0], best[1], best[2], best[3], best[4], diag

#endregion

#region Detector de avanço do Bit 47

def detect_and_parse_bit47(
    raw: str,
    after_idx: int,
    allowed_ids: Optional[Set[str]] = None,
    required_ids: Optional[Set[str]] = None,
    debug: bool = False
) -> int:
    allowed_ids = allowed_ids or set()
    required_ids = required_ids or set()
    _, _, _, endpos, _, _ = find_best_bit47_sequence(
        raw, after_idx, allowed_ids, required_ids, debug=debug
    )
    return endpos if endpos > after_idx else after_idx

#endregion

#region Parsing de campos após bitmap

FIELD_SPEC: Dict[int, Dict[str, object]] = {
    2:  {"type": "n",   "var": "llvar", "max": 19},
    3:  {"type": "n",   "len": 6},
    4:  {"type": "n",   "len": 12},
    7:  {"type": "n",   "len": 10},
    11: {"type": "n",   "len": 6},
    12: {"type": "n",   "len": 6},
    13: {"type": "n",   "len": 4},
    19: {"type": "n",   "len": 3},
    22: {"type": "n",   "len": 3},
    32: {"type": "n",   "var": "llvar", "max": 11},
    37: {"type": "ans", "len": 12},
    39: {"type": "ans", "len": 2},
    41: {"type": "ans", "len": 8},
    42: {"type": "ans", "len": 15},
    # 47: tratado in-place (LLLVAR) conforme roteiro
    49: {"type": "n",   "len": 3},
    58: {"type": "ans", "var": "lllvar", "max": 999},  # roteiro pode sobrepor max=50
    61: {"type": "ans", "var": "lllvar", "max": 999},  # roteiro pode sobrepor max=999
}
DE90_SPEC = {90: {"type": "ans", "len": 42}}          # Original Data Elements (42 AN)

def _read_fixed(s: str, pos: int, length: int) -> Tuple[str, int]:
    end = pos + length
    if end > len(s):
        raise ValueError(f"Tentativa de ler {length} chars fora do limite em pos={pos}.")
    return s[pos:end], end


def _read_var(s: str, pos: int, var_kind: str, max_len: int) -> Tuple[str, int]:
    """
    Leitor VAR tolerante a whitespace no prefixo:
      - LLVAR: se prefixo '  ' (espaços), trata como L=0;
      - LLLVAR: se prefixo '   ' (espaços), trata como L=0.
    Mantém exceção para prefixos realmente inválidos (ruído).
    """
    def _safe_int(pref: str, width: int) -> Optional[int]:
        if len(pref) < width:
            return None
        if pref.isdigit():
            return int(pref)
        if pref.strip() == "":
            return 0  # modo relaxado: whitespace -> L=0
        return None

    if var_kind == "llvar":
        if pos + 2 > len(s):
            raise ValueError("Sem espaço para prefixo LLVAR.")
        pref = s[pos:pos+2]
        L = _safe_int(pref, 2)
        if L is None:
            raise ValueError("Prefixo LLVAR não numérico.")
        pos_len_end = pos + 2

    elif var_kind == "lllvar":
        if pos + 3 > len(s):
            raise ValueError("Sem espaço para prefixo LLLVAR.")
        pref = s[pos:pos+3]
        L = _safe_int(pref, 3)
        if L is None:
            raise ValueError("Prefixo LLLVAR não numérico.")
        pos_len_end = pos + 3

    else:
        raise ValueError(f"var_kind inválido: {var_kind}")

    if L > max_len:
        L = max_len

    end = pos_len_end + L
    if end > len(s):
        raise ValueError("Valor var extrapola fim do buffer.")
    return s[pos_len_end:end], end

# ---------- DE47 in-place: lê LLLVAR do 47, quebra TLV e ID238, e avança o cursor ----------

def parse_de47_inplace(
    s: str,
    pos: int,
    used_spec: Dict[int, Dict[str, object]],
    roteiro: dict,
    *,
    out_ctx: Optional[dict] = None
) -> Tuple[Dict[str, str], List[str], int, Optional[Dict[str, str]]]:
    """
    Lê o DE47 em-place:
      1) Usa a spec ativa (esperado LLLVAR) para ler o valor bruto do 47;
      2) Quebra o TLV interno do 47 (IDs de 3 dígitos);
      3) Se houver ID '238', quebra o sub-TLV (TT+LL+VAL) e devolve as subtags;
      4) Retorna (bit47_map, bit47_order, new_pos, id238_subtags|None).
    Também popula 'out_ctx' com informações (span, maps) se fornecido.
    """
    spec47 = used_spec.get(47)
    if not spec47 or spec47.get("var") not in ("lllvar", "llvar"):
        return {}, [], pos, None

    var_kind = spec47["var"]
    max_len = int(spec47.get("max", 999))
    start = pos

    # 1) Lê o valor bruto do 47
    try:
        val47, new_pos = _read_var(s, pos, var_kind, max_len)
    except Exception:
        return {}, [], pos, None

    # 2) Quebra TLV interno do 47
    bit47_map, bit47_order = parse_tlv_payload(val47)

    # 3) ID238: sub-TLV TT+LL+VAL
    id238_subtags: Optional[Dict[str, str]] = None
    if "238" in bit47_map:
        payload_238 = bit47_map["238"]
        try:
            tag_width = int(roteiro.get("de47_id238", {}).get("subtlv", {}).get("tag_width", 2))
        except Exception:
            tag_width = 2
        try:
            id238_subtags = parse_id238_subtlv_ascii(payload_238, tag_width=tag_width, len_digits=2)
        except Exception:
            id238_subtags = None

    # 4) Popular out_ctx (se fornecido)
    if out_ctx is not None:
        out_ctx["bit47_span"] = (start, new_pos)
        out_ctx["bit47_raw"] = val47
        out_ctx["bit47_map"] = bit47_map
        out_ctx["bit47_order"] = bit47_order
        out_ctx["de47_id238_subtags"] = id238_subtags

    return bit47_map, bit47_order, new_pos, id238_subtags

# ---------- Parser de campos sequencial, com DE47 in-place ----------

def parse_bits_values_ascii(
    raw: str,
    after_idx: int,
    bits_set: Set[int],
    bit47_anchor_first_id: str = "001",
    field_spec: Optional[Dict[int, Dict[str, object]]] = None,
    out_ctx: Optional[dict] = None
) -> Tuple[Dict[str, str], int]:
    """
    Lê somente os campos conhecidos em used_spec na ORDEM dos bits setados (<=128).
    Para o Bit 47: lê in-place como LLLVAR, quebra TLV e ID238, e AVANÇA o cursor.
    """
    s = raw
    pos = after_idx
    samples: Dict[str, str] = {}

    used_spec = field_spec or FIELD_SPEC

    ordered_bits = sorted(
        b for b in bits_set
        if (b in used_spec or b == 47) and b <= 128
    )

    for b in ordered_bits:

        # --- Bit 47: in-place (LLLVAR) ---
        if b == 47:
            roteiro = load_roteiro()
            bit47_map, bit47_order, pos_after_47, id238_subtags = parse_de47_inplace(
                s, pos, used_spec, roteiro=roteiro, out_ctx=out_ctx
            )
            # Se deu certo, guardar o valor bruto do 47 e avançar
            if out_ctx and "bit47_raw" in out_ctx:
                samples["47"] = out_ctx["bit47_raw"]
            pos = pos_after_47
            continue  # segue para 49, 58, 61, 90...

        # --- Demais campos ---
        spec = used_spec.get(b)
        if not spec:
            continue

        try:
            if "len" in spec:
                val, pos = _read_fixed(s, pos, int(spec["len"]))
            elif "var" in spec:
                val, pos = _read_var(s, pos, str(spec["var"]), int(spec["max"]))
            else:
                continue

            samples[f"{b:02d}"] = val

        except Exception:
            break

    return samples, pos

#endregion

#region Heurística de seleção de MTI

def _score_main_candidate(s: str, after: int, bits: Set[int]) -> Tuple[int, Dict[str, str]]:
    score = 0
    try:
        amostras, _ = parse_bits_values_ascii(s, after, bits)
    except Exception:
        return 0, {}

    if "03" in amostras and amostras["03"].isdigit() and len(amostras["03"]) == 6:
        score += 4
    if "04" in amostras and amostras["04"].isdigit():
        score += 2
    if "07" in amostras and amostras["07"].isdigit() and len(amostras["07"]) == 10:
        score += 2
    if "11" in amostras and amostras["11"].isdigit() and len(amostras["11"]) == 6:
        score += 2
    if "12" in amostras and amostras["12"].isdigit() and len(amostras["12"]) == 6:
        score += 1
    if "13" in amostras and amostras["13"].isdigit() and len(amostras["13"]) == 4:
        score += 1
    if "41" in amostras and len(amostras["41"]) == 8:
        score += 1
    if "42" in amostras and len(amostras["42"]) == 15:
        score += 1
    if "02" in amostras and amostras["02"].isdigit():
        score += 1

    return score, amostras


def _extract_best_mti_after(s: str, mti_pat: str) -> Tuple[Optional[str], Set[int], int, str, str, int, Dict[str, str]]:
    best = (None, set(), 0, "", "", 0, {})

    # MTI com header opcional, ancorado no início da linha
    for m in re.finditer(rf'(?m)^\s*(?:\d{{6}}\s*)?({mti_pat})\s*', s):
        mti = m.group(1)
        pos = m.end(0)

        prim, pos_after_prim, _ = _read_hexN_inline_relaxed(s, pos, need=16)
        if not prim:
            prim, pos_after_prim = _read_hex16_from_next_nonempty_line(s, pos)
            if not prim:
                continue

        bits = bitmap_hex_to_setbits(prim, base_index=1)
        sec = ""
        after = pos_after_prim

        if 1 in bits:
            sec_try, pos_after_sec, consumed = _read_hexN_inline_relaxed(s, after, need=16)
            if sec_try:
                sec = sec_try
                bits |= bitmap_hex_to_setbits(sec, base_index=65)
                after = pos_after_sec
            else:
                sec_line, pos_after_sec_line = _read_hex16_from_next_nonempty_line(s, after)
                if sec_line:
                    sec = sec_line
                    bits |= bitmap_hex_to_setbits(sec, base_index=65)
                    after = pos_after_sec_line
                else:
                    after = pos_after_sec if consumed > 0 else after
                    bits.discard(1)

        sc, guess = _score_main_candidate(s, after, bits)
        if sc > best[5]:
            best = (mti, bits, after, prim, sec, sc, guess)

    return best


def extract_mti_and_bitmaps(raw: str) -> Tuple[Optional[str], Set[int], int, str, str]:
    s = raw.strip().upper()

    best = (None, set(), 0, "", "", -1, {})
    # Inclui 9600 como candidato principal para blocos isolados desse MTI,
    # sem perder prioridade dos MTIs de negocio mais comuns.
    for prefer in ("0200", "0400", "0420", "0202", "0402", "9610", "9600"):
        cand = _extract_best_mti_after(s, prefer)
        if cand[0] and cand[5] > best[5]:
            best = cand

    if best[0] and best[5] >= 5:
        return best[0], best[1], best[2], best[3], best[4]

    return None, set(), 0, "", ""

#endregion

#region Scan de fluxo 96x0/9610

def _safe_skip_de2_if_present(s: str, pos: int, bits_set: Set[int]) -> int:
    if 2 not in bits_set:
        return pos
    try:
        _, new_pos = _read_var(s, pos, "llvar", 19)
        return new_pos
    except Exception:
        return pos


def _read_de3_at(s: str, pos: int) -> Tuple[Optional[str], str]:
    cand = s[pos:pos+6]
    if len(cand) == 6 and cand.isdigit():
        return cand, "exact"
    return None, "none"


def _heuristic_find_de3(s: str, start: int, window: int = 64) -> Tuple[Optional[str], int]:
    end = min(len(s), start + window)
    sub = s[start:end]
    m = re.search(r'\b(\d{6})\b', sub)
    if m:
        return m.group(1), start + m.start(1)
    return None, -1


def scan_96x0_pcodes(raw: str) -> Tuple[Dict[str, bool], List[dict]]:
    s = raw.strip().upper()
    flags = {
        "has_96x0_940300": False,
        "has_96x0_940400": False,
        "has_96x0_940600": False,
        "has_9610_940300": False,
        "has_9610_940400": False,
        "has_9610_940600": False,
    }
    events: List[dict] = []

    for m in re.finditer(r'(?m)^\s*(?:\d{6}\s*)?(9600|9610)\s*', s):
        mti = m.group(1)
        pos = m.end(0)

        prim, pos_after_prim, _ = _read_hexN_inline_relaxed(s, pos, need=16)
        if not prim:
            prim, pos_after_prim = _read_hex16_from_next_nonempty_line(s, pos)
            if not prim:
                continue

        bits = bitmap_hex_to_setbits(prim, base_index=1)
        sec = ""
        after = pos_after_prim

        if 1 in bits:
            sec_try, pos_after_sec, consumed = _read_hexN_inline_relaxed(s, after, need=16)
            if sec_try:
                sec = sec_try
                bits |= bitmap_hex_to_setbits(sec, base_index=65)
                after = pos_after_sec
            else:
                sec_line, pos_after_sec_line = _read_hex16_from_next_nonempty_line(s, after)
                if sec_line:
                    sec = sec_line
                    bits |= bitmap_hex_to_setbits(sec, base_index=65)
                    after = pos_after_sec_line
                else:
                    after = pos_after_sec if consumed > 0 else after
                    bits.discard(1)

        pos = after

        pos_after_de2 = _safe_skip_de2_if_present(s, pos, bits)

        pcode_val, source = _read_de3_at(s, pos_after_de2)
        pcode_off = pos_after_de2
        if not pcode_val:
            pcode_val, pcode_off = _heuristic_find_de3(s, pos_after_de2, window=64)
            source = "heuristic" if pcode_val else "none"

        if pcode_val == "940300":
            flags["has_96x0_940300"] = True
            if mti == "9610":
                flags["has_9610_940300"] = True
        elif pcode_val == "940400":
            flags["has_96x0_940400"] = True
            if mti == "9610":
                flags["has_9610_940400"] = True
        elif pcode_val == "940600":
            flags["has_96x0_940600"] = True
            if mti == "9610":
                flags["has_9610_940600"] = True

        events.append({
            "mti": mti,
            "bitmap_primario_hex": prim,
            "bitmap_secundario_hex": sec if sec else "0000000000000000",
            "pcode": pcode_val,
            "pcode_source": source,
            "pcode_offset": pcode_off,
            "mti_offset": m.start(1)
        })

    return flags, events

#endregion

#region Utilitários de evento 96x0/9610

def _after_idx_from_event(raw: str, event: dict) -> Tuple[int, Set[int], str, str]:
    s = raw.strip().upper()
    prim = (event.get("bitmap_primario_hex") or "").upper()
    sec  = (event.get("bitmap_secundario_hex") or "").upper()
    mti_off = int(event.get("mti_offset", 0))

    if not prim or not re.fullmatch(r'[0-9A-F]{16}', prim):
        return -1, set(), "", ""

    bits = bitmap_hex_to_setbits(prim, base_index=1)
    after = mti_off + 4 + 16  # MTI (4) + prim (16)
    if sec and re.fullmatch(r'[0-9A-F]{16}', sec) and 1 in bits:
        bits |= bitmap_hex_to_setbits(sec, base_index=65)
        after += 16

    return after, bits, prim, (sec if sec else "0000000000000000")

#endregion

#region Extração de bits do evento 9610

def extract_9610_samples_from_event(raw: str, event: dict) -> Tuple[Dict[str, str], List[str]]:
    s = raw.strip().upper()

    prim = (event.get("bitmap_primario_hex") or "").upper()
    sec  = (event.get("bitmap_secundario_hex") or "").upper()
    mti_off = int(event.get("mti_offset", 0))

    if not prim or not re.fullmatch(r'[0-9A-F]{16}', prim):
        return {}, []

    bits = bitmap_hex_to_setbits(prim, base_index=1)
    after = mti_off + 4 + 16
    if sec and re.fullmatch(r'[0-9A-F]{16}', sec) and 1 in bits:
        bits |= bitmap_hex_to_setbits(sec, base_index=65)
        after += 16

    spec_9610 = {
        3:  {"type": "n",   "len": 6},
        7:  {"type": "n",   "len": 10},
        11: {"type": "n",   "len": 6},
        12: {"type": "n",   "len": 6},
        13: {"type": "n",   "len": 4},
        32: {"type": "n",   "var": "llvar", "max": 11},
        37: {"type": "ans", "len": 12},
        39: {"type": "ans", "len": 2},
        41: {"type": "ans", "len": 8},
        42: {"type": "ans", "len": 15},
        90: {"type": "ans", "len": 42},
    }

    samples: Dict[str, str] = {}
    bits_pres: List[str] = []
    pos = after

    for b in sorted(bits):
        if b > 64:
            continue
        if b not in spec_9610:
            continue
        spec = spec_9610[b]
        try:
            if "len" in spec:
                val, pos = _read_fixed(s, pos, int(spec["len"]))
            elif spec.get("var") == "llvar":
                val, pos = _read_var(s, pos, "llvar", int(spec["max"]))
            else:
                continue
            samples[f"{b:02d}"] = val
            bits_pres.append(f"{b:02d}")
        except Exception:
            break

    return samples, bits_pres

#endregion

#region Seleção de cenário

def _ctx_get_field(ctx: dict, path: str):
    overrides = ctx.get("_overrides") or {}
    if path in overrides:
        return overrides[path]

    if path == "mti":
        return ctx.get("mti")
    if path.startswith("bit."):
        k = path.split(".", 1)[1].zfill(2)
        return (ctx.get("amostras_bits") or {}).get(k)
    if path.startswith("47."):
        kid = path.split(".", 1)[1]
        return (ctx.get("bit47_map") or {}).get(kid)
    if path.startswith("flow."):
        key = path.split(".", 1)[1]
        return (ctx.get("flow_flags") or {}).get(key)
    return None


def _eval_condition(cond: dict, ctx: dict) -> bool:
    if cond.get("always") is True:
        return True

    field = cond.get("field")
    if not field:
        return False

    if "exists" in cond:
        return (_ctx_get_field(ctx, field) is not None) if cond["exists"] else (_ctx_get_field(ctx, field) is None)

    if "not_exists" in cond:
        return (_ctx_get_field(ctx, field) is None) if cond["not_exists"] else (_ctx_get_field(ctx, field) is not None)

    val = _ctx_get_field(ctx, field)
    if val is None:
        return False

    ignore_case = cond.get("ignore_case", True)
    if ignore_case and isinstance(val, str):
        val_cmp = val.lower()
    else:
        val_cmp = val

    if "equals" in cond:
        cmp = cond["equals"]
        if ignore_case and isinstance(cmp, str):
            cmp = cmp.lower()
        return val_cmp == cmp

    if "one_of" in cond and isinstance(cond["one_of"], list):
        opts = cond["one_of"]
        if ignore_case:
            opts = [o.lower() if isinstance(o, str) else o for o in opts]
        return val_cmp in opts

    if "contains" in cond and isinstance(val_cmp, str):
        sub = cond["contains"]
        if ignore_case and isinstance(sub, str):
            sub = sub.lower()
        return sub in val_cmp

    if "startswith" in cond and isinstance(val_cmp, str):
        pref = cond["startswith"]
        if ignore_case and isinstance(pref, str):
            pref = pref.lower()
        return val_cmp.startswith(pref)

    if "regex" in cond and isinstance(val_cmp, str):
        try:
            return re.search(cond["regex"], val_cmp) is not None
        except re.error:
            return False

    return False


def select_scenario_from_roteiro(
    roteiro: dict,
    mti: Optional[str],
    amostras_bits: dict,
    bit47_map: dict,
    flow_flags: dict,
    *,
    force_scenario_name: Optional[str] = None,
    ctx_overrides: Optional[dict] = None
) -> dict:
    default_cfg = {
        "name": "DEFAULT",
        "required_bits": roteiro.get("required_bits", []),
        "required_bit47_ids": roteiro.get("required_bit47_ids", []),
        "bit47_allowed_ids": roteiro.get("bit47_allowed_ids", []),
        "required_id238_tags": [],
        "bit47_id_rules": {}
    }

    scenarios = roteiro.get("scenarios", [])
    if not scenarios:
        return default_cfg

    if force_scenario_name:
        for sc in scenarios:
            if sc.get("name") == force_scenario_name:
                return {
                    "name": sc.get("name", "SCENARIO"),
                    "required_bits": sc.get("required_bits", default_cfg["required_bits"]),
                    "required_bit47_ids": sc.get("required_bit47_ids", default_cfg["required_bit47_ids"]),
                    "bit47_allowed_ids": sc.get("bit47_allowed_ids", default_cfg["bit47_allowed_ids"]),
                    "required_id238_tags": sc.get("required_id238_tags", default_cfg["required_id238_tags"]),
                    "bit47_id_rules": sc.get("bit47_id_rules", default_cfg["bit47_id_rules"])
                }

    ctx = {
        "mti": mti,
        "amostras_bits": amostras_bits or {},
        "bit47_map": bit47_map or {},
        "flow_flags": flow_flags or {},
        "_overrides": ctx_overrides or {}
    }

    for sc in scenarios:
        when = sc.get("when", [])
        if all(_eval_condition(c, ctx) for c in when):
            return {
                "name": sc.get("name", "SCENARIO"),
                "required_bits": sc.get("required_bits", default_cfg["required_bits"]),
                "required_bit47_ids": sc.get("required_bit47_ids", default_cfg["required_bit47_ids"]),
                "bit47_allowed_ids": sc.get("bit47_allowed_ids", default_cfg["bit47_allowed_ids"]),
                "required_id238_tags": sc.get("required_id238_tags", default_cfg["required_id238_tags"]),
                "bit47_id_rules": sc.get("bit47_id_rules", default_cfg["bit47_id_rules"])
            }

    return default_cfg

#endregion

#region Construção de FIELD_SPEC ativo

def build_field_spec_from_roteiro(
    roteiro: dict,
    scenario_cfg: dict,
    mti: Optional[str]
) -> Dict[int, Dict[str, object]]:
    spec = dict(FIELD_SPEC)  # base

    # 1) Aplicar formatos do roteiro (se houver)
    fmt = roteiro.get("field_formats", {})
    for k, conf in fmt.items():
        try:
            b = int(k)
        except:
            continue
        t = (conf.get("type") or "").lower()
        charset = (conf.get("charset") or "").lower()
        if t == "fixed":
            spec[b] = {
                "type": "n" if charset == "numeric" else "ans",
                "len": int(conf.get("len", 0))
            }
        elif t == "llvar":
            spec[b] = {
                "type": "ans",
                "var": "llvar",
                "max": int(conf.get("max", 99)),
                "min": int(conf.get("min", 0)),
            }
        elif t == "lllvar":
            spec[b] = {
                "type": "ans",
                "var": "lllvar",
                "max": int(conf.get("max", 999)),
                "min": int(conf.get("min", 0)),
            }

    # 2) DE90 só quando cenário pedir
    required_bits = set(scenario_cfg.get("required_bits", []))
    wants_90 = ("90" in required_bits)
    if wants_90:
        spec.update(DE90_SPEC)
    else:
        spec.pop(90, None)

    return spec


def _validate_formatted_field_against_spec(bit: str, value: str, spec: Dict[str, object]) -> List[str]:
    errors: List[str] = []
    shown_bit = str(bit).zfill(2)
    val = str(value or "")
    field_type = str(spec.get("type") or "").lower()

    if field_type == "n" and val and not val.isdigit():
        errors.append(f"Bit {shown_bit}: esperado numérico, recebido '{val}'")

    if "len" in spec:
        expected_len = int(spec.get("len", 0))
        if len(val) != expected_len:
            errors.append(f"Bit {shown_bit}: tamanho {len(val)} != {expected_len} (exato)")
        return errors

    min_len = spec.get("min")
    max_len = spec.get("max")
    if min_len is not None and len(val) < int(min_len):
        errors.append(f"Bit {shown_bit}: tamanho {len(val)} < {int(min_len)}")
    if max_len is not None and len(val) > int(max_len):
        errors.append(f"Bit {shown_bit}: tamanho {len(val)} > {int(max_len)}")

    return errors


def _validate_formatted_fields_against_spec(
    fields: Dict[str, str],
    field_spec: Dict[int, Dict[str, object]],
) -> List[str]:
    errors: List[str] = []
    if not fields or not field_spec:
        return errors

    for bit, value in sorted(fields.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 9999):
        bit_str = str(bit).zfill(2)
        if not bit_str.isdigit():
            continue
        bit_int = int(bit_str)
        spec = field_spec.get(bit_int)
        if not spec:
            continue
        errors.extend(_validate_formatted_field_against_spec(bit_str, str(value or ""), spec))

    return errors

#endregion

#region Validador principal

def validar_iso_0200_raw(
    texto: str,
    cliente: str = "LOCAL",
    debug: bool = False,
    *,
    cenario_forcado: Optional[str] = None,
    forcar_cartao: bool = False,
    forcar_pct: bool = False
) -> dict:
    roteiro = load_roteiro()
    allowed_mtis = set(roteiro.get("allowed_mtis", []))

    erros: List[str] = []
    avisos: List[str] = []
    passed: List[str] = []

    # 1) Mensagem principal
    mti, bits_set, after_idx, prim_hex, sec_hex = extract_mti_and_bitmaps(texto)
    bits_presentes = {str(b).zfill(2) for b in bits_set if b <= 128}

    # 2) MTI permitido
    if not mti:
        avisos.append("MTI principal (0200/0400/0420/0202/0402/9610) não foi localizado de forma plausível neste log.")
    elif allowed_mtis and (mti not in allowed_mtis) and not (mti == "0402" and "0400" in allowed_mtis):
        erros.append(f"MTI '{mti}' não permitido pelo roteiro (esperados: {sorted(allowed_mtis)}).")
    else:
        passed.append("MTI")

    if prim_hex:
        passed.append(f"BITMAP_PRIMARIO({prim_hex})")
        if sec_hex:
            passed.append(f"BITMAP_SECUNDARIO({sec_hex})")

    # 3) Parsing inicial com SPEC default (rápido)
    try:
        amostras_bits, pos_consumido = parse_bits_values_ascii(
            texto, after_idx, bits_set, bit47_anchor_first_id="001", field_spec=None
        )
    except Exception:
        amostras_bits, pos_consumido = ({}, after_idx)

    # 4) FLUXO 96x0/9610 (flags/pcodes)
    flow_flags, flow_events = scan_96x0_pcodes(texto)

    # 4.1) Fallback: se não há MTI principal mas há 9610/9600, extrair amostras do evento
    samples_source = None
    overrides = {}
    used_9610_fallback = False
    chosen_evt = None

    if not mti and flow_events:
        evt = None
        # Prioriza 9610, que representa a resposta relevante do cliente.
        for e in flow_events:
            if e.get("mti") == "9610" and e.get("pcode") == "940400":
                evt = e; break
        if not evt:
            for e in flow_events:
                if e.get("mti") == "9610" and e.get("pcode") == "940600":
                    evt = e; break
        if not evt:
            for e in flow_events:
                if e.get("mti") == "9610":
                    evt = e; break
        if not evt:
            for e in flow_events:
                if e.get("mti") == "9600" and e.get("pcode") == "940400":
                    evt = e; break
        if not evt:
            for e in flow_events:
                if e.get("mti") == "9600" and e.get("pcode") == "940600":
                    evt = e; break
        if not evt:
            for e in flow_events:
                if e.get("mti") == "9600":
                    evt = e; break

        if evt:
            amostras_bits_9610, bits_presentes_9610 = extract_9610_samples_from_event(texto, evt)
            if amostras_bits_9610:
                amostras_bits = amostras_bits_9610
                bits_presentes = set(bits_presentes_9610)
                samples_source = "9610_fallback"
                mti = str(evt.get("mti") or mti or "") or None
                overrides["mti"] = evt.get("mti")  # ajuda o seletor de cenário
                if evt.get("pcode"):
                    amostras_bits["03"] = evt["pcode"]

                used_9610_fallback = True
                chosen_evt = evt

    # 4.2) Bit 47 – preferir DE47 in-place no reparse (se houver MTI principal)
    bit47_map_raw: Dict[str, str] = {}
    bit47_order_raw: List[str] = []
    start_pos = end_pos = -1
    score = 0
    diag: List[dict] = []
    bit47_extracted_by = None

    required_bit47_ids_default = set(roteiro.get("required_bit47_ids", []))
    allowed_bit47_ids_default = set(roteiro.get("bit47_allowed_ids", []))

    # 6) Selecionar cenário
    scenario_cfg = select_scenario_from_roteiro(
        roteiro, mti, amostras_bits, bit47_map_raw, flow_flags,
        force_scenario_name=cenario_forcado,
        ctx_overrides=overrides
    )

    # 6.1) Construir FIELD_SPEC ativo
    FIELD_SPEC_ACTIVE = build_field_spec_from_roteiro(roteiro, scenario_cfg, mti)

    # 6.2) Reparse com SPEC ativo (apenas quando temos MTI principal)
    out_ctx = {}
    try:
        if not used_9610_fallback:
            amostras_bits, pos_consumido = parse_bits_values_ascii(
                texto, after_idx, bits_set,
                bit47_anchor_first_id="001",
                field_spec=FIELD_SPEC_ACTIVE,
                out_ctx=out_ctx
            )
        else:
            pos_consumido = None
    except Exception:
        pass

    # Se o in-place trouxe 47 (quando MTI principal), use-o
    if out_ctx.get("bit47_map"):
        bit47_map_raw = dict(out_ctx["bit47_map"])
        bit47_order_raw = list(out_ctx.get("bit47_order") or [])
        if out_ctx.get("bit47_span"):
            start_pos, end_pos = out_ctx["bit47_span"]
        bit47_extracted_by = "principal_inplace"
    else:
        # Em 9610_fallback, tentar ler DE47 in-place a partir do evento (se 47 setado)
        if used_9610_fallback and chosen_evt:
            evt_after, evt_bits_set, evt_prim_hex, evt_sec_hex = _after_idx_from_event(texto, chosen_evt)
            if evt_after != -1 and 47 in evt_bits_set:
                spec_for_47 = dict(FIELD_SPEC_ACTIVE)
                if 47 not in spec_for_47:
                    spec_for_47[47] = {"type": "ans", "var": "lllvar", "max": 999}

                out_ctx_47 = {}
                try:
                    _, _ = parse_bits_values_ascii(
                        texto,
                        evt_after,
                        evt_bits_set,
                        bit47_anchor_first_id="001",
                        field_spec=spec_for_47,
                        out_ctx=out_ctx_47
                    )
                except Exception:
                    out_ctx_47 = {}

                bit47_map_fallback = dict(out_ctx_47.get("bit47_map") or {})
                bit47_order_fallback = list(out_ctx_47.get("bit47_order") or [])

                if bit47_order_fallback:
                    bit47_map_raw = bit47_map_fallback
                    bit47_order_raw = bit47_order_fallback
                    start_pos, end_pos = out_ctx_47.get("bit47_span", (-1, -1))
                    bit47_extracted_by = "96x0_inplace"
        else:
            # Fallback heurístico (se MTI principal existe)
            if mti:
                allowed_prefilter = allowed_bit47_ids_default | required_bit47_ids_default
                bit47_map_raw, bit47_order_raw, start_pos, end_pos, score, diag = find_best_bit47_sequence(
                    texto, after_idx, allowed_prefilter, required_bit47_ids_default, debug=debug
                )
                bit47_extracted_by = "principal_fallback" if bit47_order_raw else None

    # 7) Validar bits obrigatórios (do cenário) com downgrade para >64 sem secundário válido
    required_bits = set(scenario_cfg["required_bits"])
    required_bit47_ids = set(scenario_cfg["required_bit47_ids"])
    allowed_bit47_ids = set(scenario_cfg["bit47_allowed_ids"])
    bit47_id_rules = scenario_cfg.get("bit47_id_rules") or {}

    de03_eff = amostras_bits.get("03")
    if _skip_bit37_validation(mti, de03_eff):
        required_bits.discard("37")

    if mti:
        has_secondary = bool(re.fullmatch(r'[0-9A-F]{16}', sec_hex)) and (1 in bits_set)

        faltantes_bits = []
        downgraded_bits = []

        for b in sorted(required_bits):
            try:
                bi = int(b)
            except:
                continue
            if bi > 64 and not has_secondary:
                downgraded_bits.append(b)
                continue

            # Neste validador, o campo "01" representa o MTI da mensagem
            # (não apenas o bit 1 do bitmap primário).
            bit_presente = (b in bits_presentes)
            if bi == 1 and mti:
                bit_presente = True

            if not bit_presente:
                faltantes_bits.append(b)

        if faltantes_bits:
            erros.append(f"Bits obrigatórios ausentes: {', '.join(faltantes_bits)}")

        if downgraded_bits:
            avisos.append(
                f"Bitmap secundário ausente/truncado: não é possível exigir os bits {', '.join(downgraded_bits)} (ex.: 90)."
            )

        if not faltantes_bits:
            passed.append("BITS_PRESENCA")
    else:
        avisos.append("Sem MTI principal plausível, validação de presença de bits foi limitada ao scanner 96x0.")

    # 8) Filtrar Bit 47 (allowed ∪ required); em debug inclui todos
    allowed_post = allowed_bit47_ids | required_bit47_ids
    if debug:
        allowed_post |= set(bit47_map_raw.keys())

    if allowed_post:
        bit47_map = {k: v for k, v in bit47_map_raw.items() if k in allowed_post}
        bit47_order = [i for i in bit47_order_raw if i in allowed_post]
    else:
        bit47_map = dict(bit47_map_raw)
        bit47_order = list(bit47_order_raw)

    # 9) Validar Bit 47 (IDs obrigatórios do cenário)
    if not bit47_order:
        needs_bit47 = ("47" in required_bits) or bool(required_bit47_ids)
        if not needs_bit47:
            pass
        elif mti:
            avisos.append("Bit 47 (TLV) não detectado de forma confiável (ancorado em DE47 LLLVAR).")
        else:
            avisos.append("Bit 47 (TLV) não foi encontrado via fallback 96x0/9610.")
    else:
        mtis_first_id_001 = set(roteiro.get("bit47_first_id_001_mtis", []))
        enforce_first_id_001 = (mti in mtis_first_id_001)
        if enforce_first_id_001:
            if bit47_order[0] != "001":
                erros.append(f"Bit 47: o primeiro ID deve ser '001', mas o primeiro encontrado foi '{bit47_order[0]}'.")
            else:
                passed.append("BIT47_FIRST_ID_OK")
        else:
            passed.append("BIT47_FIRST_ID_NA")

        faltando_subids = [sid for sid in sorted(required_bit47_ids) if sid not in bit47_map]
        if faltando_subids:
            erros.append(f"Bit 47: sub-IDs obrigatórios ausentes: {', '.join(faltando_subids)}")
        else:
            if required_bit47_ids:
                passed.append("BIT47_SUBIDS")

        rule_errors = validate_bit47_id_rules(bit47_map, bit47_id_rules)
        if rule_errors:
            erros.extend(rule_errors)
        elif bit47_id_rules:
            passed.append("BIT47_SUBIDS_FORMAT")

    # 10) Validar ID 238 (sub-TLV) se presente
    subtags_238 = None
    try:
        subtags_238 = validate_id238_if_present(
            bit47_map=bit47_map,
            profile=roteiro,
            amostras_bits=amostras_bits,
            scenario=scenario_cfg,
            errors_sink=erros,
            debug=debug
        )
    except Exception as e:
        erros.append(f"DE47/ID238: erro inesperado na validação: {e}")

    aprovado = len(erros) == 0
    status = "APROVADO" if aprovado else "REPROVADO"

    # Amostras do 47 (human-readable) e RAW (para depuração)
    amostras47 = {k: (v[:60] + ("..." if len(v) > 60 else "")) for k, v in bit47_map.items()}
    bit47_raw_ids = list(bit47_order_raw)
    amostras47_raw = {k: (v[:120] + ("..." if len(v) > 120 else "")) for k, v in bit47_map_raw.items()}

    # Preview das subtags do 238
    subtags_238_preview = None
    subtags_238_keys = None
    if subtags_238:
        subtags_238_preview = {k: (v[:120] + ("..." if len(v) > 120 else "")) for k, v in subtags_238.items()}
        subtags_238_keys = sorted(list(subtags_238.keys()))

    # Ajustar bitmaps mostrados quando viemos de 9610_fallback
    if used_9610_fallback and chosen_evt:
        prim_hex_evt = (chosen_evt.get("bitmap_primario_hex") or "").upper()
        sec_hex_evt  = (chosen_evt.get("bitmap_secundario_hex") or "0000000000000000").upper()
    else:
        prim_hex_evt = prim_hex
        sec_hex_evt  = sec_hex if sec_hex else "0000000000000000"

    # Montagem do resultado
    result = {
        "teste": roteiro.get("teste", "ISO 8583 – Validador Multi-MTI com Cenários"),
        "versao": "1.9.9",
        "cliente": cliente,
        "status": status,
        "aprovado": aprovado,
        "regras_passadas": passed,
        "erros": erros,
        "avisos": avisos,
        "detalhes_execucao": {
            "cenario_selecionado": scenario_cfg.get("name", "DEFAULT"),
            "mti": mti,
            "bitmap_primario_hex": prim_hex_evt,
            "bitmap_secundario_hex": sec_hex_evt,
            "bits_presentes": sorted(list(bits_presentes)),
            "amostras_bits": amostras_bits,
            "samples_source": (samples_source or ("principal" if mti else None)),
            "flow_flags": flow_flags,
            "flow_events": flow_events[:50],
            "bit47_inicio": start_pos,
            "bit47_fim": end_pos,
            "bit47_score": score,
            "bit47_ids_encontrados_ordem": bit47_order,
            "bit47_subids_presentes": sorted(list(bit47_map.keys())),
            "amostras_bit47": amostras47,
            "bit47_raw_ids_encontrados_ordem": bit47_raw_ids,
            "amostras_bit47_raw": amostras47_raw,
            "bit47_origem": (
                "principal_inplace" if (bit47_map and bit47_extracted_by == "principal_inplace")
                else ("principal" if (bit47_map and bit47_extracted_by == "principal_fallback")
                    else ((f"{mti}_inplace") if (bit47_map and bit47_extracted_by == "96x0_inplace" and mti)
                        else ((mti or "96x0") if (bit47_map and not bit47_extracted_by and mti)
                            else ("96x0" if (bit47_map and not mti) else None))))
            ),
            "comprimento_log": len(texto),
            "bit47_id238_subtags_presentes": subtags_238_keys,
            "bit47_id238_subtags": (subtags_238_preview),
        }
    }

    if debug:
        result["debug"] = {
            "after_idx_bitmap": after_idx,
            "pos_consumido_campos": locals().get("pos_consumido"),
            "scenario_cfg": scenario_cfg,
            "bits_set_list": sorted([b for b in bits_set if b <= 128]),
            "has_secondary_bitmap": (bool(re.fullmatch(r'[0-9A-F]{16}', sec_hex)) and (1 in bits_set)),
            "field_spec_active_keys": sorted(list(FIELD_SPEC_ACTIVE.keys())),
            "used_9610_fallback": used_9610_fallback,
        }

    return result

#endregion

#region Parser de log ISO formatado

def _looks_like_raw_iso_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    # Prefixo comum no ambiente: 6 dígitos de header + MTI
    return re.match(r'^\d{6}(0200|0201|0202|0210|0212|0400|0401|0402|0410|0412|0420|9600|9610)[0-9A-F]', s) is not None


def parse_iso_formatted_blocks(texto: str) -> List[dict]:
    """
    Extrai blocos ISO de logs no formato auditado:
      - Linha de cabeçalho contendo "ISO . FEPAS:";
      - Linha seguinte com string ISO bruta;
      - Linhas de campos formatados (ex.: "11 (  6): [009837]").
    """
    lines = texto.splitlines()
    n = len(lines)
    i = 0
    blocks: List[dict] = []

    while i < n:
        line = lines[i]
        if "ISO . FEPAS:" not in line:
            i += 1
            continue

        direction = "unknown"
        up = line.upper()
        if "MENSAGEM RECEBIDA" in up:
            direction = "in"
        elif "MENSAGEM  ENVIADA" in up or "MENSAGEM ENVIADA" in up:
            direction = "out"

        raw_iso = None
        raw_line_no = None

        j = i + 1
        # Procura a primeira linha plausível de ISO bruto até o próximo cabeçalho ISO
        while j < n:
            lj = lines[j]
            if "ISO . FEPAS:" in lj:
                break
            if _looks_like_raw_iso_line(lj):
                raw_iso = lj.strip()
                raw_line_no = j + 1
                break
            j += 1

        fields: Dict[str, str] = {}
        tlv_ids: Dict[str, List[str]] = {}
        tlv_map: Dict[str, Dict[str, str]] = {}
        current_tlv_bit: Optional[str] = None
        last_field_bit: Optional[str] = None
        last_tlv_id: Optional[str] = None
        k = (j + 1) if raw_iso is not None else (i + 1)

        while k < n:
            lk = lines[k]
            if "ISO . FEPAS:" in lk:
                break

            mt = re.match(r'^\s*\[TLV\s*-\s*Bit:(\d+)\s*\(\d+\)\]\s*$', lk)
            if mt:
                current_tlv_bit = mt.group(1).zfill(2)
                tlv_ids.setdefault(current_tlv_bit, [])
                tlv_map.setdefault(current_tlv_bit, {})
                last_field_bit = None
                last_tlv_id = None
                k += 1
                continue

            mtlv = re.match(r'^\s*(\d{3})\s*\(\s*\d+\)\s*:?\s*\[(.*)\]\s*$', lk)
            if mtlv and current_tlv_bit:
                id3 = mtlv.group(1)
                val3 = mtlv.group(2)
                ids = tlv_ids.setdefault(current_tlv_bit, [])
                if id3 not in ids:
                    ids.append(id3)
                tlv_map.setdefault(current_tlv_bit, {})[id3] = val3
                last_field_bit = None
                last_tlv_id = id3
                k += 1
                continue

            mcont = re.match(r'^\s*\[(.*)\]\s*$', lk)
            if mcont:
                cont = mcont.group(1)
                if current_tlv_bit and last_tlv_id:
                    prev = tlv_map.setdefault(current_tlv_bit, {}).get(last_tlv_id, "")
                    tlv_map[current_tlv_bit][last_tlv_id] = prev + cont
                    k += 1
                    continue
                if last_field_bit:
                    prev = fields.get(last_field_bit, "")
                    fields[last_field_bit] = prev + cont
                    k += 1
                    continue

            mf = re.match(r'^\s*(\d{1,3})\s*\(\s*\d+\):\s*\[(.*)\]\s*$', lk)
            if mf:
                b = mf.group(1).zfill(2)
                fields[b] = mf.group(2)
                current_tlv_bit = None
                last_field_bit = b
                last_tlv_id = None
            else:
                mid = re.match(r'^\s*(\d{3})\s*\(\s*\d+\)\s*\[.*\]\s*$', lk)
                if mid and current_tlv_bit:
                    id3 = mid.group(1)
                    ids = tlv_ids.setdefault(current_tlv_bit, [])
                    if id3 not in ids:
                        ids.append(id3)
            k += 1

        if raw_iso is not None or fields:
            blocks.append({
                "header_line": i + 1,
                "header_text": line.strip(),
                "direction": direction,
                "raw_iso_line": raw_line_no,
                "raw_iso": raw_iso,
                "fields": fields,
                "tlv_ids": tlv_ids,
                "tlv_map": tlv_map,
            })

        i = k if k > i else i + 1

    return blocks


def _is_leg_of_interest(mti: Optional[str], de03: Optional[str]) -> bool:
    return mti in ("0200", "0202", "0400", "0402", "0420", "9610")


def _is_timeout_leg(mti: Optional[str], de03: Optional[str]) -> bool:
    """Perna de timeout que deve ser suprimida da saída."""
    return (mti in ("9600", "9610")) and (str(de03 or "") == "940300")


def _skip_bit37_validation(mti: Optional[str], de03: Optional[str]) -> bool:
    """
    No fluxo 940400 (9600/9610), o DE37 não deve ser validado
    nem como obrigatório nem como opcional.
    """
    return (mti in ("9600", "9610")) and (str(de03 or "") == "940400")


def validar_log_iso_formatado(
    texto: str,
    cliente: str = "LOCAL",
    debug: bool = False,
    *,
    cenario_forcado: Optional[str] = None,
    forcar_cartao: bool = False,
    forcar_pct: bool = False,
    filtro_de11: Optional[str] = None,
    filtro_de41: Optional[str] = None,
    apenas_pernas_interesse: bool = True,
) -> dict:
    roteiro = load_roteiro()
    blocks = parse_iso_formatted_blocks(texto)

    legs: List[dict] = []
    warnings: List[str] = []
    errors: List[str] = []

    for idx, block in enumerate(blocks, start=1):
        raw_iso = block.get("raw_iso")
        fields = block.get("fields") or {}
        tlv_ids_block = block.get("tlv_ids") or {}
        tlv_map_block = block.get("tlv_map") or {}

        validation: Dict[str, Any]
        validacao_executada = False
        if raw_iso:
            validation = validar_iso_0200_raw(
                raw_iso,
                cliente=cliente,
                debug=debug,
                cenario_forcado=cenario_forcado,
                forcar_cartao=forcar_cartao,
                forcar_pct=forcar_pct,
            )
            validacao_executada = True
        else:
            validation = {
                "status": "NAO_VALIDADO",
                "aprovado": None,
                "erros": [],
                "avisos": ["Bloco ISO sem string bruta: validação individual não executada."],
                "detalhes_execucao": {"mti": None, "amostras_bits": {}},
            }

        det = validation.get("detalhes_execucao") or {}
        amostras = det.get("amostras_bits") or {}

        mti = fields.get("01") or det.get("mti")
        de03 = fields.get("03") or amostras.get("03")
        de11 = fields.get("11") or amostras.get("11")
        de41 = fields.get("41") or amostras.get("41")

        key = f"{de11}|{de41}" if de11 and de41 else None

        campos_bits = dict(fields)
        if "01" not in campos_bits and mti:
            campos_bits["01"] = mti
        for b, v in amostras.items():
            campos_bits.setdefault(str(b).zfill(2), v)

        interesse = _is_leg_of_interest(mti, de03)

        bit47_ids_fmt = list(tlv_ids_block.get("47") or [])
        bit47_map_fmt: Dict[str, str] = dict(tlv_map_block.get("47") or {})
        bit47_map_out: Dict[str, str] = dict(bit47_map_fmt or det.get("amostras_bit47") or {})
        bit47_ids_out = list(bit47_ids_fmt or det.get("bit47_ids_encontrados_ordem") or [])
        bit47_map_raw_out: Dict[str, str] = dict(det.get("amostras_bit47_raw") or {})
        bit47_ids_raw_out = list(det.get("bit47_raw_ids_encontrados_ordem") or [])

        if not bit47_map_out:
            raw47 = campos_bits.get("47")
            if isinstance(raw47, str) and raw47:
                m47, o47 = parse_tlv_payload(raw47)
                bit47_map_out = m47
                if not bit47_ids_out:
                    bit47_ids_out = o47

        if not bit47_map_raw_out:
            raw47 = campos_bits.get("47")
            if isinstance(raw47, str) and raw47:
                m47_raw, o47_raw = parse_tlv_payload(raw47)
                bit47_map_raw_out = m47_raw
                if not bit47_ids_raw_out:
                    bit47_ids_raw_out = o47_raw

        if not bit47_ids_out:
            if bit47_map_out:
                bit47_ids_out = list(bit47_map_out.keys())
            else:
                bit47_ids_out = bit47_ids_fmt

        if not bit47_ids_raw_out:
            if bit47_map_raw_out:
                bit47_ids_raw_out = list(bit47_map_raw_out.keys())
            else:
                bit47_ids_raw_out = bit47_ids_fmt

        leg_status = validation.get("status")
        leg_aprovado = validation.get("aprovado")
        leg_erros_raw = list(validation.get("erros") or [])
        leg_erros = list(leg_erros_raw)
        leg_avisos = list(validation.get("avisos") or [])

        scenario_cfg_fmt = select_scenario_from_roteiro(
            roteiro,
            mti,
            campos_bits,
            bit47_map_out,
            det.get("flow_flags") or {},
            force_scenario_name=cenario_forcado,
        )
        field_spec_active = build_field_spec_from_roteiro(roteiro, scenario_cfg_fmt, mti)

        if _skip_bit37_validation(mti, de03):
            field_spec_active.pop(37, None)

        formatted_errors = _validate_formatted_fields_against_spec(campos_bits, field_spec_active)

        if bit47_map_out:
            formatted_errors.extend(
                validate_bit47_id_rules(bit47_map_out, scenario_cfg_fmt.get("bit47_id_rules") or {})
            )
            try:
                validate_id238_if_present(
                    bit47_map=bit47_map_out,
                    profile=roteiro,
                    amostras_bits=campos_bits,
                    scenario=scenario_cfg_fmt,
                    errors_sink=formatted_errors,
                    debug=False,
                )
            except Exception as e:
                formatted_errors.append(f"DE47/ID238: erro inesperado na validação formatada: {e}")

        leg_erros_formatados = list(formatted_errors)

        if formatted_errors:
            for msg in formatted_errors:
                if msg not in leg_erros:
                    leg_erros.append(msg)
            leg_status = "REPROVADO"
            leg_aprovado = False

        # Suprime pernas de timeout (96x0 pcode 940300) da saída final.
        if _is_timeout_leg(mti, de03):
            continue

        legs.append({
            "idx": idx,
            "header_line": block.get("header_line"),
            "raw_iso_line": block.get("raw_iso_line"),
            "raw_iso": raw_iso,
            "direction": block.get("direction"),
            "mti": mti,
            "de03": de03,
            "de11": de11,
            "de41": de41,
            "chave_match_11_41": key,
            "status": leg_status,
            "aprovado": leg_aprovado,
            "validacao_executada": validacao_executada,
            "perna_interesse": interesse,
            "erros_raw": leg_erros_raw,
            "erros_formatados": leg_erros_formatados,
            "erros": leg_erros,
            "avisos": leg_avisos,
            "cenario": scenario_cfg_fmt.get("name") or det.get("cenario_selecionado"),
            "bits": campos_bits,
            "bit47_map_fmt": bit47_map_fmt,
            "bit47_ids_fmt": bit47_ids_fmt,
            "bit47_ids": bit47_ids_out,
            "bit47_map": bit47_map_out,
            "bit47_ids_raw": bit47_ids_raw_out,
            "bit47_map_raw": bit47_map_raw_out,
            "bit47_origem": det.get("bit47_origem"),
        })

    legs_all = list(legs)
    if apenas_pernas_interesse:
        legs = [l for l in legs if l.get("perna_interesse")]

    grouped_all: Dict[str, List[dict]] = {}
    for leg in legs_all:
        key = leg.get("chave_match_11_41")
        if not key:
            continue
        grouped_all.setdefault(key, []).append(leg)

    grouped: Dict[str, List[dict]] = {}
    sem_chave: List[dict] = []

    for leg in legs:
        key = leg.get("chave_match_11_41")
        if not key:
            sem_chave.append(leg)
            continue
        grouped.setdefault(key, []).append(leg)

    transacoes: List[dict] = []
    for key, tlegs in grouped.items():
        tlegs_sorted = sorted(tlegs, key=lambda x: x.get("header_line") or 0)
        tlegs_all_sorted = sorted(grouped_all.get(key, tlegs_sorted), key=lambda x: x.get("header_line") or 0)
        has_0200 = any((l.get("mti") == "0200") for l in tlegs_sorted)
        has_0400 = any((l.get("mti") == "0400") for l in tlegs_sorted)
        has_96x0_940400 = any((l.get("mti") in ("9600", "9610") and l.get("de03") == "940400") for l in tlegs_sorted)
        validated = [l for l in tlegs_sorted if l.get("validacao_executada")]
        all_approved = all(bool(l.get("aprovado")) for l in validated)

        transacoes.append({
            "chave_match_11_41": key,
            "de11": tlegs_sorted[0].get("de11"),
            "de41": tlegs_sorted[0].get("de41"),
            "quantidade_pernas": len(tlegs_sorted),
            "pernas_validadas": len(validated),
            "status": "APROVADO" if all_approved else "REPROVADO",
            "aprovado": all_approved,
            "tem_0200": has_0200,
            "tem_0400": has_0400,
            "tem_96x0_940400": has_96x0_940400,
            "pernas": tlegs_sorted,
            "pernas_todas": tlegs_all_sorted,
        })

    transacoes.sort(key=lambda x: (x["pernas"][0].get("header_line") or 0))

    transacoes_antes_filtro = len(transacoes)
    if filtro_de11 or filtro_de41:
        transacoes = [
            t for t in transacoes
            if ((not filtro_de11) or (t.get("de11") == filtro_de11))
            and ((not filtro_de41) or (t.get("de41") == filtro_de41))
        ]

        if not transacoes:
            errors.append(
                f"Nenhuma transação encontrada para filtro DE11={filtro_de11 or '*'} e DE41={filtro_de41 or '*'}"
            )

    if sem_chave:
        warnings.append(f"{len(sem_chave)} bloco(s) sem DE11/DE41 completos ficaram fora do match.")

    if filtro_de11 or filtro_de41:
        legs_scope = [p for t in transacoes for p in t.get("pernas", [])]
    else:
        legs_scope = legs

    total_legs = len(legs_scope)
    total_validadas = sum(1 for l in legs_scope if l.get("validacao_executada"))
    total_aprovadas = sum(1 for l in legs_scope if l.get("validacao_executada") and l.get("aprovado") is True)
    total_reprovadas = sum(1 for l in legs_scope if l.get("validacao_executada") and l.get("aprovado") is False)
    total_nao_validadas = total_legs - total_validadas

    if total_nao_validadas:
        warnings.append(f"{total_nao_validadas} bloco(s) foram correlacionados, mas sem string bruta para validação individual.")

    if total_reprovadas:
        errors.append(f"{total_reprovadas} perna(s) ISO reprovada(s) na validação individual.")

    transacao_selecionada = transacoes[0] if len(transacoes) == 1 else None
    transacoes_saida = [] if transacao_selecionada is not None else transacoes

    aprovado_geral = (total_reprovadas == 0) and not any(e.startswith("Nenhuma transação encontrada") for e in errors)

    return {
        "teste": "ISO 8583 – Validação por Log Formatado",
        "versao": "1.9.9",
        "cliente": cliente,
        "status": "APROVADO" if aprovado_geral else "REPROVADO",
        "aprovado": aprovado_geral,
        "erros": errors,
        "avisos": warnings,
        "resumo": {
            "blocos_iso_encontrados": len(legs_all),
            "blocos_perna_interesse": total_legs,
            "blocos_validados": total_validadas,
            "blocos_aprovados": total_aprovadas,
            "blocos_reprovados": total_reprovadas,
            "blocos_nao_validados": total_nao_validadas,
            "transacoes_match_11_41": len(transacoes),
            "transacoes_match_11_41_antes_filtro": transacoes_antes_filtro,
            "blocos_sem_chave_11_41": len(sem_chave),
        },
        "filtro_aplicado": {
            "de11": filtro_de11,
            "de41": filtro_de41,
            "apenas_pernas_interesse": apenas_pernas_interesse,
        },
        "transacao_selecionada": transacao_selecionada,
        "transacoes": transacoes_saida,
        "blocos_sem_chave": sem_chave,
    }

#endregion

#region Homologação interativa

def _get_homolog_tests(roteiro: dict) -> Dict[str, dict]:
    tests = roteiro.get("homolog_tests") or {}
    out: Dict[str, dict] = {}
    for k, v in tests.items():
        tid = str(k).zfill(2)
        if isinstance(v, dict):
            cfg = dict(v)
            cfg.setdefault("id", tid)
            out[tid] = cfg
    return out


def _ler_input_obrigatorio(prompt: str) -> str:
    while True:
        valor = input(prompt).strip()
        if valor:
            return valor
        print("Valor obrigatório. Tente novamente.")


def _selecionar_teste_homologacao(homolog_tests: Dict[str, dict]) -> str:
    print("\n=== Seleção de Teste de Homologação ===")
    for tid in sorted(homolog_tests.keys()):
        t = homolog_tests[tid]
        print(f"{t['id']} - {t['nome']} | Objetivo: {t['objetivo_esperado']}")

    while True:
        escolha = _ler_input_obrigatorio("\nInforme o teste (ex.: 01): ")
        escolha = escolha.zfill(2)
        if escolha in homolog_tests:
            return escolha
        print("Teste inválido. Informe um teste listado.")


def _ler_de11_de41_interativo() -> Tuple[str, str]:
    while True:
        de11 = _ler_input_obrigatorio("Informe o Bit 11 (6 dígitos): ")
        if de11.isdigit() and len(de11) == 6:
            break
        print("Bit 11 inválido. Use exatamente 6 dígitos numéricos.")

    while True:
        de41 = _ler_input_obrigatorio("Informe o Bit 41 (8 caracteres): ").upper()
        if len(de41) == 8:
            break
        print("Bit 41 inválido. Use exatamente 8 caracteres.")

    return de11, de41


def _ler_log_homologacao() -> str:
    def _normalizar_path(raw: str) -> str:
        p = raw.strip()
        if p.lower().startswith("cd "):
            p = p[3:].strip()
        if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
            p = p[1:-1].strip()
        return p

    def _selecionar_arquivo_em_pasta(dir_path: str) -> Optional[str]:
        try:
            entries = sorted(os.listdir(dir_path))
        except Exception:
            return None

        files = []
        for name in entries:
            full = os.path.join(dir_path, name)
            if os.path.isfile(full):
                files.append(full)

        if not files:
            return None

        print("\nPasta informada. Selecione o arquivo de log:")
        for idx, fp in enumerate(files, start=1):
            print(f"{idx:02d} - {os.path.basename(fp)}")

        while True:
            escolha = _ler_input_obrigatorio("Número do arquivo: ")
            if escolha.isdigit():
                n = int(escolha)
                if 1 <= n <= len(files):
                    return files[n - 1]
            print("Seleção inválida. Informe um número da lista.")

    def _resolver_path_log(path: str) -> str:
        # Mantém suporte a caminho absoluto e, para caminho relativo/nome de arquivo,
        # tenta a pasta padrão de logs ao lado do script.
        if os.path.isabs(path):
            return path

        candidate_default = os.path.join(DEFAULT_LOGS_DIR, path)
        if os.path.exists(candidate_default):
            return candidate_default

        return os.path.abspath(path)

    if os.path.isdir(DEFAULT_LOGS_DIR):
        print(f"Pasta padrão de logs: {DEFAULT_LOGS_DIR}")

    while True:
        raw_path = _ler_input_obrigatorio(
            "Informe o caminho do arquivo de log (ou só o nome do arquivo): "
        )
        path = _normalizar_path(raw_path)

        if not path:
            print("Caminho vazio. Informe um arquivo de log válido.")
            continue

        path = _resolver_path_log(path)

        if os.path.isdir(path):
            escolhido = _selecionar_arquivo_em_pasta(path)
            if not escolhido:
                print("A pasta informada não possui arquivos para leitura.")
                continue
            path = escolhido

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except FileNotFoundError:
            print("Arquivo não encontrado. Informe um caminho válido.")
        except Exception as e:
            print(f"Não foi possível ler o arquivo: {e}")


def _coletar_mtis_da_transacao(transacao: dict) -> List[str]:
    pernas = sorted(
        transacao.get("pernas_todas") or transacao.get("pernas", []),
        key=lambda x: x.get("header_line") or 0,
    )
    mtis: List[str] = []
    for p in pernas:
        mti = p.get("mti")
        if mti and mti not in mtis:
            mtis.append(mti)
    return mtis


def _buscar_transacao_por_chave(resultado_log: dict, de11: str, de41: str) -> Optional[dict]:
    transacoes = []
    if resultado_log.get("transacao_selecionada"):
        transacoes.append(resultado_log["transacao_selecionada"])
    transacoes.extend(resultado_log.get("transacoes") or [])

    for t in transacoes:
        if str(t.get("de11") or "") == de11 and str(t.get("de41") or "") == de41:
            return t
    return None


def _extrair_id283_da_perna(perna: dict) -> str:
    bit47_map_raw = perna.get("bit47_map_raw") or {}
    id283_raw = str(bit47_map_raw.get("283") or "")
    if id283_raw:
        return id283_raw

    bit47_map = perna.get("bit47_map") or {}
    id283 = str(bit47_map.get("283") or "")
    if id283:
        return id283

    bits = perna.get("bits") or {}
    raw47 = str(bits.get("47") or "")
    if raw47:
        try:
            m47, _ = parse_tlv_payload(raw47)
            return str(m47.get("283") or "")
        except Exception:
            return ""
    return ""


def _extrair_id_tlv_do_bit(perna: dict, bit: int, id_tag: str) -> str:
    """
    Extrai um TLV de um bit específico, considerando:
    - TAG: 3 dígitos (ex: 505, 506)
    - LEN: 2-3 dígitos decimais (ex: 629)
    - VALUE: conforme LEN
    
    Robusto contra quebra de linhas no payload (remove-as antes de processar).
    """
    bits = perna.get("bits") or {}
    raw = str(bits.get(str(bit)) or bits.get(bit) or "")
    if not raw:
        return ""

    sid = str(id_tag)
    
    # Remove quebras de linha para parser robusto.
    raw_clean = raw.replace("\n", "").replace("\r", "").strip()
    if not raw_clean:
        return ""

    # Tentativa 1: parser TLV estrito no payload limpo.
    try:
        mapa, _ = parse_tlv_payload(raw_clean)
        val = str(mapa.get(sid) or "")
        if val:
            return val
    except Exception:
        pass

    # Tentativa 2: parser TLV leniente (tolerante a desalinhamento).
    try:
        mapa_v, _ = _parse_tlv_visual_best(raw_clean)
        val = str(mapa_v.get(sid) or "")
        if val:
            return val
    except Exception:
        pass

    # Tentativa 3: busca manual TAG + LEN(3) + VALUE
    # Procura padrão: 3 dígitos (TAG) + até 3 dígitos (LEN) + valor.
    pos = raw_clean.find(sid)
    if pos != -1:
        pos_len = pos + len(sid)
        
        # Tenta LLL (3 dígitos)
        if pos_len + 3 <= len(raw_clean) and raw_clean[pos_len:pos_len+3].isdigit():
            ln_str = raw_clean[pos_len:pos_len+3]
            try:
                ln = int(ln_str)
                if ln > 0:
                    val_start = pos_len + 3
                    val_end = val_start + ln
                    if val_end <= len(raw_clean):
                        return raw_clean[val_start:val_end]
                    else:
                        # Se não tem bytes suficientes, retorna o máximo conhecimento.
                        return raw_clean[val_start:]
            except Exception:
                pass
        
        # Tenta LL (2 dígitos)
        if pos_len + 2 <= len(raw_clean) and raw_clean[pos_len:pos_len+2].isdigit():
            ln_str = raw_clean[pos_len:pos_len+2]
            try:
                ln = int(ln_str)
                if ln > 0:
                    val_start = pos_len + 2
                    val_end = val_start + ln
                    if val_end <= len(raw_clean):
                        return raw_clean[val_start:val_end]
                    else:
                        return raw_clean[val_start:]
            except Exception:
                pass

    # Tentativa 4: regex TAG + LEN(2/3) + payload (fallback).
    m = re.search(rf"{re.escape(sid)}(\d{{2,3}})(.*)", raw_clean, re.DOTALL)
    if m:
        try:
            ln = int(m.group(1))
            if ln > 0:
                resto = str(m.group(2) or "")
                return resto[:ln] if len(resto) >= ln else resto
        except Exception:
            pass

    return ""


def _extrair_id506_bit48(perna: dict) -> str:
    return _extrair_id_tlv_do_bit(perna, 48, "506")


def _extrair_id505_bit62(perna: dict) -> str:
    return _extrair_id_tlv_do_bit(perna, 62, "505")


def _extrair_id506_bit48_apos_segundo_arroba(perna: dict) -> str:
    bits = perna.get("bits") or {}
    raw48 = str(bits.get("48") or "")
    if not raw48:
        return ""

    partes = raw48.split("@", 2)
    payload = partes[2] if len(partes) >= 3 else ""
    if not payload:
        return ""

    # Tentativa 1: parser TLV principal.
    try:
        m48, _ = parse_tlv_payload(payload)
        v506 = str(m48.get("506") or "")
        if v506:
            return v506
    except Exception:
        pass

    # Tentativa 2: parser visual leniente.
    try:
        m48v, _ = _parse_tlv_visual_best(payload)
        v506 = str(m48v.get("506") or "")
        if v506:
            return v506
    except Exception:
        pass

    # Tentativa 3: fallback por regex (TAG 506 + LEN decimal 2/3).
    m = re.search(r"506(\d{2,3})(.*)", payload)
    if not m:
        return ""
    try:
        ln = int(m.group(1))
    except Exception:
        return ""
    resto = str(m.group(2) or "")
    if ln <= 0:
        return ""
    return resto[:ln] if len(resto) >= ln else resto


def _extrair_texto_bit48_apos_segundo_arroba(perna: dict) -> str:
    bits = perna.get("bits") or {}
    raw48 = str(bits.get("48") or "")
    if not raw48:
        return ""

    partes = raw48.split("@", 2)
    texto = partes[2] if len(partes) >= 3 else ""
    return str(texto or "").strip()


def _extrair_texto_id505_bit62(perna: dict) -> str:
    return str(_extrair_id505_bit62(perna) or "").strip()


def _extrair_texto_bit62_apos_segundo_arroba(perna: dict) -> str:
    bits = perna.get("bits") or {}
    raw62 = str(bits.get("62") or "")
    if not raw62:
        return ""
    partes = raw62.split("@", 2)
    texto = partes[2] if len(partes) >= 3 else ""
    return str(texto or "").strip()


def _tipo_por_texto_bit48(texto: str) -> Optional[str]:
    t = str(texto or "").upper()
    if not t:
        return None
    if re.search(r"CR[ÉE]DITO", t):
        return "credito"
    if re.search(r"D[ÉE]BITO", t):
        return "debito"
    return None


def _tipo_por_id283(id283: str) -> Optional[str]:
    if not id283:
        return None
    if id283.startswith("01"):
        return "credito"
    if id283.startswith("02"):
        return "debito"
    return None


def _parse_versao_bit61(value: str) -> Optional[Tuple[int, int]]:
    """
    Converte versão no formato NN.NN (ex.: 10.44) para tupla comparável (10, 44).
    """
    if not value:
        return None
    v = value.strip()
    if not re.fullmatch(r"\d{2}\.\d{2}", v):
        return None
    try:
        major = int(v[:2])
        minor = int(v[3:5])
        return (major, minor)
    except Exception:
        return None


def _extrair_versao_bit61_da_perna(perna: dict) -> Optional[str]:
    """
    A versão é lida nos 5 primeiros caracteres do Bit 61, incluindo o ponto.
    Exemplo: '10.44...'
    """
    bits = perna.get("bits") or {}
    raw61 = str(bits.get("61") or bits.get(61) or "")
    if len(raw61) < 5:
        return None
    versao = raw61[:5]
    return versao if _parse_versao_bit61(versao) else None


def _extrair_versao_bit61_transacao(pernas: List[dict]) -> Optional[str]:
    for p in sorted(pernas, key=lambda x: x.get("header_line") or 0):
        v = _extrair_versao_bit61_da_perna(p)
        if v:
            return v
    return None


def _tipo_por_prefixo(prefix_map: Dict[str, str], valor_id: str) -> Optional[str]:
    if not valor_id:
        return None
    for pref, label in prefix_map.items():
        if str(valor_id).startswith(str(pref)):
            return str(label)
    return None


def _tipo_por_tag01_compacto(prefix_map: Dict[str, str], valor_id: str) -> Optional[str]:
    """
    Alguns IDs (ex.: 253/283) podem vir em formato compacto TAG/VALOR de 2 dígitos,
    como "01020103...", em que TAG 01 tem valor "02" (débito).
    Neste caso, o tipo deve ser lido pelo valor da TAG 01, não pelo prefixo bruto.
    """
    raw = str(valor_id or "").strip()
    if not raw or len(raw) < 4:
        return None
    if not raw.isdigit() or (len(raw) % 2) != 0:
        return None

    for i in range(0, len(raw) - 1, 2):
        tag = raw[i:i + 2]
        val = raw[i + 2:i + 4]
        if tag == "01":
            mapped = prefix_map.get(val)
            return str(mapped) if mapped else None
    return None


def _descricao_fonte_tipo(source_kind: str, id_fonte: str) -> str:
    sk = str(source_kind or "").strip().lower()
    if sk == "bit48_text_after_second_at":
        return "texto do Bit 48 após o segundo @"
    if sk == "bit62_text_after_second_at":
        return "texto do Bit 62 após o segundo @ (fallback ID505/Bit48-ID506)"
    if sk == "bit62_text_from_id505":
        return "texto do ID 505 no Bit 62 (via cliente)"
    if sk == "bit48_id506":
        return "ID 506 no Bit 48"
    if sk == "bit48_id506_after_second_at":
        return "ID 506 no Bit 48 após o segundo @"
    if sk == "bit62_id505":
        return "ID 505 no Bit 62 (via cliente)"
    if str(id_fonte or "") == "253":
        return "ID 253 do Bit 47"
    if str(id_fonte or "") == "283":
        return "ID 283 do Bit 47"
    return f"fonte {id_fonte}" if id_fonte else "fonte configurada"


def _extrair_id47_da_perna(perna: dict, id47: str) -> str:
    sid = str(id47)

    bit47_map_fmt = perna.get("bit47_map_fmt") or {}
    if sid in bit47_map_fmt:
        return str(bit47_map_fmt.get(sid) or "")

    bit47_map_raw = perna.get("bit47_map_raw") or {}
    if sid in bit47_map_raw:
        return str(bit47_map_raw.get(sid) or "")

    bit47_map = perna.get("bit47_map") or {}
    if sid in bit47_map:
        return str(bit47_map.get(sid) or "")

    bits = perna.get("bits") or {}
    raw47 = str(bits.get("47") or "")
    if raw47:
        try:
            m47, _ = parse_tlv_payload(raw47)
            return str(m47.get(sid) or "")
        except Exception:
            return ""

    return ""


def _step_matches(perna: dict, step: dict) -> bool:
    mti = str(perna.get("mti") or "")
    de03 = str(perna.get("de03") or "")
    bits = perna.get("bits") or {}

    step_mti = step.get("mti")
    if step_mti and mti != str(step_mti):
        return False

    step_any_mti = step.get("any_mti")
    if isinstance(step_any_mti, list) and step_any_mti:
        opts = {str(x) for x in step_any_mti}
        if mti not in opts:
            return False

    if "de03" in step and de03 != str(step.get("de03") or ""):
        return False

    step_any_de03 = step.get("any_de03")
    if isinstance(step_any_de03, list) and step_any_de03:
        opts_de03 = {str(x) for x in step_any_de03}
        if de03 not in opts_de03:
            return False

    step_de03_ne = step.get("de03_ne")
    if step_de03_ne:
        if de03 == str(step_de03_ne):
            return False

    if "de39" in step:
        de39 = str(bits.get("39") or "")
        if de39 != str(step.get("de39") or ""):
            return False

    # Validação opcional de IDs do Bit 47 no próprio passo da cadeia.
    # Exemplo:
    # "bit47": { "023": "02" }
    step_bit47 = step.get("bit47")
    if isinstance(step_bit47, dict) and step_bit47:
        for sid, expected in step_bit47.items():
            atual = _extrair_id47_da_perna(perna, str(sid))
            if atual != str(expected):
                return False

    # Validação opcional de negação de IDs do Bit 47.
    # Exemplo:
    # "bit47_ne": { "023": "02" }  -> reprova quando ID 023 for diferente de 02
    step_bit47_ne = step.get("bit47_ne")
    if isinstance(step_bit47_ne, dict) and step_bit47_ne:
        for sid, expected in step_bit47_ne.items():
            atual = _extrair_id47_da_perna(perna, str(sid))
            if atual == "":
                return False
            if atual == str(expected):
                return False

    return True


def _find_matching_step_index(pernas: List[dict], step: dict, search_from: int = 0) -> Optional[int]:
    occurrence_raw = (step or {}).get("occurrence", 1)
    try:
        occurrence = int(occurrence_raw)
    except (TypeError, ValueError):
        occurrence = 1

    if occurrence < 1:
        occurrence = 1

    seen = 0
    for i in range(max(0, search_from), len(pernas)):
        if _step_matches(pernas[i], step):
            seen += 1
            if seen == occurrence:
                return i

    return None


def _find_chain_indexes(pernas: List[dict], required_chain: List[dict]) -> Tuple[Optional[List[int]], List[str]]:
    erros: List[str] = []
    if not required_chain:
        return [], erros

    indexes: List[int] = []
    search_from = 0

    for idx_step, step in enumerate(required_chain, start=1):
        found = None
        for i in range(search_from, len(pernas)):
            if _step_matches(pernas[i], step):
                found = i
                break
        if found is None:
            if bool(step.get("optional", False)):
                continue
            label = step.get("label") or f"passo_{idx_step}"
            erros.append(f"Cadeia esperada não encontrada: {label}.")
            return None, erros
        indexes.append(found)
        search_from = found + 1

    return indexes, erros


def _extrair_valor_ref(perna: dict, ref: dict) -> str:
    if "bit" in ref:
        bit = str(ref.get("bit") or "").zfill(2)
        if bit == "03":
            v = str(perna.get("de03") or "")
            if v:
                return v
        bits = perna.get("bits") or {}
        return str(bits.get(bit) or bits.get(str(int(bit))) or "")

    if "bit47_id" in ref:
        sid = str(ref.get("bit47_id") or "")
        return _extrair_id47_da_perna(perna, sid)

    field = str(ref.get("field") or "")
    if field == "mti":
        return str(perna.get("mti") or "")
    if field == "de11":
        return str(perna.get("de11") or "")
    if field == "de03":
        return str(perna.get("de03") or "")
    if field == "de39":
        bits = perna.get("bits") or {}
        return str(bits.get("39") or "")
    if field == "de90_original_stan":
        return str(_extrair_stan_original_de90(perna) or "")

    return ""


def _avaliar_comparacoes(pernas: List[dict], comparacoes: List[dict]) -> List[str]:
    erros: List[str] = []
    if not comparacoes:
        return erros

    for idx, comp in enumerate(comparacoes, start=1):
        label = str(comp.get("label") or f"comparacao_{idx}")
        op = str(comp.get("operator") or "==")
        left_ref = comp.get("left") or {}
        right_ref = comp.get("right") or {}

        left_idx = _find_matching_step_index(pernas, left_ref)
        right_idx = _find_matching_step_index(pernas, right_ref)

        if left_idx is None:
            erros.append(f"Comparação '{label}': perna LEFT não encontrada.")
            continue
        if right_idx is None:
            erros.append(f"Comparação '{label}': perna RIGHT não encontrada.")
            continue

        left_val = _extrair_valor_ref(pernas[left_idx], left_ref)
        right_val = _extrair_valor_ref(pernas[right_idx], right_ref)

        if left_val == "":
            erros.append(f"Comparação '{label}': valor LEFT vazio/ausente.")
            continue
        if right_val == "":
            erros.append(f"Comparação '{label}': valor RIGHT vazio/ausente.")
            continue

        if op == "==":
            ok = left_val == right_val
        elif op == "!=":
            ok = left_val != right_val
        elif op in {"<", ">", "<=", ">="}:
            if not left_val.isdigit() or not right_val.isdigit():
                erros.append(
                    f"Comparação '{label}': operador '{op}' requer valores numéricos (LEFT='{left_val}', RIGHT='{right_val}')."
                )
                continue

            li = int(left_val)
            ri = int(right_val)
            if op == "<":
                ok = li < ri
            elif op == ">":
                ok = li > ri
            elif op == "<=":
                ok = li <= ri
            else:
                ok = li >= ri
        else:
            erros.append(f"Comparação '{label}': operador '{op}' não suportado.")
            continue

        if not ok:
            erros.append(
                f"Comparação '{label}' falhou: LEFT='{left_val}' {op} RIGHT='{right_val}'"
            )

    return erros


def _avaliar_any_of_conditions(pernas: List[dict], any_of_conditions: List[dict]) -> List[str]:
    erros: List[str] = []
    if not any_of_conditions:
        return erros

    for idx, group in enumerate(any_of_conditions, start=1):
        if not isinstance(group, dict):
            continue

        options = group.get("one_of") or []
        if not isinstance(options, list) or not options:
            continue

        matched = False
        for option in options:
            if not isinstance(option, dict):
                continue
            if any(_step_matches(perna, option) for perna in pernas):
                matched = True
                break

        if matched:
            continue

        label = str(group.get("label") or f"regra_or_{idx}")
        option_labels: List[str] = []
        for opt_idx, option in enumerate(options, start=1):
            if isinstance(option, dict):
                option_labels.append(_label_from_step(option, opt_idx))

        if option_labels:
            detalhe = "; ".join(option_labels)
            erros.append(
                f"Regra obrigatória (OU) não atendida: {label}. Atenda ao menos uma condição: {detalhe}."
            )
        else:
            erros.append(f"Regra obrigatória (OU) não atendida: {label}.")

    return erros


def _parse_tlv_payload_leniente(payload: str, start: int = 0) -> Tuple[Dict[str, str], List[str]]:
    """
    Parser TLV para visualização (mais tolerante que o parser estrito):
      - TAG: 3 dígitos
      - LEN: tenta LLL e depois LL
      - Se LEN exceder o restante, captura o restante e encerra.
    """
    s = str(payload or "")
    n = len(s)
    pos = max(0, int(start))
    out: Dict[str, str] = {}
    order: List[str] = []

    while pos + 5 <= n:
        tag = s[pos:pos+3]
        if not tag.isdigit():
            break

        pos_len = pos + 3
        L: Optional[int] = None
        len_digits = 0

        if pos_len + 3 <= n and s[pos_len:pos_len+3].isdigit():
            L = int(s[pos_len:pos_len+3])
            len_digits = 3
        elif pos_len + 2 <= n and s[pos_len:pos_len+2].isdigit():
            L = int(s[pos_len:pos_len+2])
            len_digits = 2
        else:
            break

        val_start = pos_len + len_digits
        if L is None or L < 0:
            break

        val_end = val_start + L
        if val_end > n:
            val = s[val_start:n]
            if tag not in out:
                order.append(tag)
                out[tag] = val
            else:
                out[tag] += val
            break

        val = s[val_start:val_end]
        if tag not in out:
            order.append(tag)
            out[tag] = val
        else:
            out[tag] += val
        pos = val_end

    return out, order


def _score_tlv_visual(order: List[str]) -> int:
    if not order:
        return 0
    common = {"001", "006", "007", "008", "009", "016", "041", "042", "046", "060", "071", "200", "201", "238", "400"}
    present_common = sum(1 for x in order if x in common)
    # Penaliza fortemente parse com apenas 1 ID (normalmente sinal de desalinhamento).
    starts_ok = 60 if order and order[0] == "001" else 0
    bad_start = -120 if order and order[0] in {"720", "833", "880"} else 0
    return (len(order) * 10) + (present_common * 30) + starts_ok + bad_start - (50 if len(order) == 1 else 0)


def _parse_tlv_visual_best(payload: str) -> Tuple[Dict[str, str], List[str]]:
    s = str(payload or "")
    best_map: Dict[str, str] = {}
    best_order: List[str] = []
    best_score = -10**9

    candidate_offsets = {0, 1, 2, 3, 4}

    # Tenta localizar inícios plausíveis de sequência TLV conhecidos no payload.
    for token in ("001", "006", "007", "008", "009", "041", "042", "200", "201", "238", "400"):
        pos = s.find(token)
        while pos != -1:
            candidate_offsets.add(pos)
            pos = s.find(token, pos + 1)

    # Tenta offsets comuns (campo pode vir com prefixo/tamanho residual no começo).
    for off in sorted(x for x in candidate_offsets if x < len(s)):
        if off >= len(s):
            continue
        m1, o1 = _parse_tlv_payload_leniente(s, start=off)
        sc1 = _score_tlv_visual(o1)
        if sc1 > best_score:
            best_map, best_order, best_score = m1, o1, sc1

    # Se ficou um único ID grande, tenta quebrar o valor interno como nested TLV.
    if len(best_order) == 1:
        inner = str(best_map.get(best_order[0]) or "")
        nested_best_map: Dict[str, str] = {}
        nested_best_order: List[str] = []
        nested_best_score = -10**9
        for off in (0, 1, 2, 3):
            if off >= len(inner):
                continue
            m2, o2 = _parse_tlv_payload_leniente(inner, start=off)
            sc2 = _score_tlv_visual(o2)
            if sc2 > nested_best_score:
                nested_best_map, nested_best_order, nested_best_score = m2, o2, sc2

        if nested_best_score > _score_tlv_visual(best_order):
            return nested_best_map, nested_best_order

    return best_map, best_order


def _parse_id238_visual_best(payload: str) -> Tuple[Dict[str, str], List[str]]:
    s = str(payload or "")
    try:
        subtags = parse_id238_subtlv_ascii(s, tag_width=2, len_digits=2)
        order = list(subtags.keys())
        return subtags, order
    except Exception:
        pass

    out: Dict[str, str] = {}
    order: List[str] = []
    i = 0
    n = len(s)
    while i + 4 <= n:
        tag = s[i:i+2]
        ll = s[i+2:i+4]
        if not tag.isdigit() or not ll.isdigit():
            break
        L = int(ll)
        start = i + 4
        end = start + L
        if end > n:
            val = s[start:n]
            out[tag] = val
            order.append(tag)
            break
        val = s[start:end]
        out[tag] = val
        order.append(tag)
        i = end
    return out, order


def _formatar_iso_perna(
    bits: Dict[str, Any],
    mti: str,
    bit47_map_fmt: Optional[Dict[str, str]] = None,
    bit47_ids_fmt: Optional[List[str]] = None,
    bit47_map_raw: Optional[Dict[str, str]] = None,
    bit47_ids_raw: Optional[List[str]] = None,
) -> str:
    """
    Formata os campos da perna em layout legível por linha:
      1 (  4): [0200]
      3 (  6): [006000]
      ...
    """
    linhas: List[str] = []
    mti_txt = str(mti or "")
    if mti_txt:
        linhas.append(f"  1 (  4): [{mti_txt}]")

    items: List[Tuple[int, str]] = []
    for k, v in (bits or {}).items():
        ks = str(k).strip()
        if not ks.isdigit():
            continue
        bi = int(ks)
        if bi == 1:
            continue
        items.append((bi, str(v)))

    for bi, val in sorted(items, key=lambda x: x[0]):
        linhas.append(f"{bi:>3} ({len(val):>3}): [{val}]")

    # Se houver Bit 47, exibe também os IDs TLV quebrados em linhas.
    mapa_47: Dict[str, str] = dict(bit47_map_fmt or {})
    ordem_47: List[str] = [str(x) for x in (bit47_ids_fmt or []) if str(x) in mapa_47]

    raw_47 = str((bits or {}).get("47") or "")
    if not mapa_47 and raw_47:
        try:
            mapa_47, ordem_47 = _parse_tlv_visual_best(raw_47)
        except Exception:
            mapa_47, ordem_47 = ({}, [])

    # Fallback para mapa pré-extraído quando o parse local não encontrou IDs.
    if not mapa_47:
        mapa_47 = dict(bit47_map_raw or {})
        ordem_47 = [str(x) for x in (bit47_ids_raw or []) if str(x) in mapa_47]

    if mapa_47:
        linhas.append("[TLV - Bit:47]")
        if not ordem_47:
            ordem_47 = sorted(str(k) for k in mapa_47.keys())
        for sid in ordem_47:
            sval = str(mapa_47.get(sid) or "")
            linhas.append(f"ID {sid} ({len(sval):>3}) [{sval}]")

            if sid == "238" and sval:
                sub238_map, sub238_order = _parse_id238_visual_best(sval)
                if sub238_map:
                    linhas.append("  [SubTLV - ID:238]")
                    for subid in sub238_order:
                        subval = str(sub238_map.get(subid) or "")
                        linhas.append(f"  TAG {subid} ({len(subval):>3}) [{subval}]")

    # Exibe IDs TLV dos Bits 48/62 quando aplicável (ex.: IDs 506/505).
    # Tenta extrair conhecidos: Bit 48 → ID 506, Bit 62 → ID 505.
    bit_id_map = {48: "506", 62: "505"}
    for bit, known_id in bit_id_map.items():
        raw_val = str((bits or {}).get(str(bit).zfill(2)) or (bits or {}).get(str(bit)) or "")
        if not raw_val:
            continue
        
        # Tenta extrair o ID conhecido direto.
        id_val = _extrair_id_tlv_do_bit({"bits": {str(bit): raw_val}}, bit, known_id)
        if id_val:
            linhas.append(f"[TLV - Bit:{bit}]")
            linhas.append(f"ID {known_id} ({len(id_val):>3}) [{id_val}]")

    return "\n".join(linhas)


def _avaliar_cadeias_completas_transacao(pernas: List[dict]) -> List[str]:
    erros: List[str] = []
    if not pernas:
        return erros

    tem_0200 = any(str(p.get("mti") or "") == "0200" for p in pernas)
    tem_0400 = any(str(p.get("mti") or "") == "0400" for p in pernas)
    tem_0201 = any(str(p.get("mti") or "") == "0201" for p in pernas)
    tem_0401 = any(str(p.get("mti") or "") == "0401" for p in pernas)
    tem_940600 = any(_step_matches(p, {"mti": "9610", "de03": "940600"}) for p in pernas)

    if tem_0200:
        if tem_940600:
            chain_compra_cartao = [
                {"label": "0200", "mti": "0200"},
                {"label": "9610 pcode 940400", "mti": "9610", "de03": "940400"},
                {"label": "9610 pcode 940600", "mti": "9610", "de03": "940600"},
                {"label": "0210", "mti": "0210"},
                {"label": "0202", "mti": "0202"},
                {"label": "0212", "mti": "0212"},
            ]
            _, e = _find_chain_indexes(pernas, chain_compra_cartao)
            erros.extend([f"Fluxo obrigatório compra cartão: {x}" for x in e])
        else:
            chain_compra_pct = [
                {"label": "0200", "mti": "0200"},
                {"label": "9610 pcode 940400", "mti": "9610", "de03": "940400"},
                {"label": "0210", "mti": "0210"},
                {"label": "0202", "mti": "0202"},
                {"label": "0212", "mti": "0212"},
            ]
            _, e = _find_chain_indexes(pernas, chain_compra_pct)
            erros.extend([f"Fluxo obrigatório compra PCT: {x}" for x in e])

    if tem_0400:
        chain_cancelamento = [
            {"label": "0400", "mti": "0400"},
            {"label": "0410", "mti": "0410"},
            {"label": "0402", "mti": "0402"},
            {"label": "0412", "mti": "0412"},
        ]
        _, e = _find_chain_indexes(pernas, chain_cancelamento)
        erros.extend([f"Fluxo obrigatório cancelamento: {x}" for x in e])

    if tem_0201:
        chain_consulta_compra = [
            {"label": "0201", "mti": "0201"},
            {"label": "0210", "mti": "0210"},
            {"label": "0202", "mti": "0202"},
            {"label": "0212", "mti": "0212"},
        ]
        _, e = _find_chain_indexes(pernas, chain_consulta_compra)
        erros.extend([f"Fluxo obrigatório consulta compra: {x}" for x in e])

    if tem_0401:
        chain_consulta_cancelamento = [
            {"label": "0401", "mti": "0401"},
            {"label": "0410", "mti": "0410"},
            {"label": "0402", "mti": "0402"},
            {"label": "0412", "mti": "0412"},
        ]
        _, e = _find_chain_indexes(pernas, chain_consulta_cancelamento)
        erros.extend([f"Fluxo obrigatório consulta cancelamento: {x}" for x in e])

    return erros


def _build_ignore_leg_status_refs(rule: dict, required_chain: List[dict], teste_id: str = "") -> List[dict]:
    """Monta refs de pernas que devem aparecer no fluxo, mas sem aprovar/reprovar."""
    refs: List[dict] = []

    configured = rule.get("ignore_leg_status") or []
    if isinstance(configured, list):
        for ref in configured:
            if isinstance(ref, dict):
                refs.append(dict(ref))

    # Regra padrão para compras (cadeia com 0200): 9600/940400 não conta status.
    # Exceção: em modo "presence_only_required_chain", pernas do objetivo devem poder aprovar por presença.
    presence_only_required_chain = bool(rule.get("presence_only_required_chain", False))
    has_0200 = any(str((step or {}).get("mti") or "") == "0200" for step in (required_chain or []))
    if has_0200 and not presence_only_required_chain:
        default_ref = {"mti": "9600", "de03": "940400"}
        if not any(
            str(r.get("mti") or "") == "9600" and str(r.get("de03") or "") == "940400"
            for r in refs
            if isinstance(r, dict)
        ):
            refs.append(default_ref)

    # Teste 01: quando houver 9600/940600 fora do objetivo, também não deve validar.
    if str(teste_id).zfill(2) == "01":
        default_ref_t01 = {"mti": "9600", "de03": "940600"}
        if not any(
            str(r.get("mti") or "") == "9600" and str(r.get("de03") or "") == "940600"
            for r in refs
            if isinstance(r, dict)
        ):
            refs.append(default_ref_t01)

    # Regra específica do teste 12:
    # 0410 e 0412 contam apenas por presença no fluxo (sem aprovar/reprovar por bits/IDs).
    if str(teste_id).zfill(2) == "12":
        for mti_presence_only in ("0410", "0412"):
            if not any(
                str(r.get("mti") or "") == mti_presence_only
                for r in refs
                if isinstance(r, dict)
            ):
                refs.append({"mti": mti_presence_only})

    return refs


def _build_ignore_leg_campos_refs(rule: dict) -> List[dict]:
    """Monta refs de pernas que nao entram na validacao de dados (bits/IDs), mas contam no fluxo."""
    refs: List[dict] = []

    configured = rule.get("ignore_leg_campos_bits") or []
    if isinstance(configured, list):
        for ref in configured:
            if isinstance(ref, dict):
                refs.append(dict(ref))

    return refs


def _rule_has_reversal_0400(required_chain: List[dict]) -> bool:
    return any(str((step or {}).get("mti") or "") == "0400" for step in (required_chain or []))


def _is_pcode_validation_error(msg: Any) -> bool:
    text = str(msg or "").lower()
    return (
        "bit 03" in text
        or "de03" in text
        or "campo 03" in text
        or "pcode" in text
    )


def _sanitize_reversal_pcode_validation(pernas: List[dict], required_chain: List[dict]) -> List[dict]:
    if not _rule_has_reversal_0400(required_chain):
        return pernas

    sanitized: List[dict] = []
    target_mtis = {"0400", "0410", "0412"}

    for perna in pernas:
        mti = str(perna.get("mti") or "")
        if mti not in target_mtis:
            sanitized.append(perna)
            continue

        erros = list(perna.get("erros") or [])
        erros_raw = list(perna.get("erros_raw") or [])
        erros_formatados = list(perna.get("erros_formatados") or [])
        all_errors = [str(e) for e in (erros + erros_raw + erros_formatados) if str(e or "").strip()]

        filtered_erros = [e for e in erros if not _is_pcode_validation_error(e)]
        filtered_erros_raw = [e for e in erros_raw if not _is_pcode_validation_error(e)]
        filtered_erros_formatados = [e for e in erros_formatados if not _is_pcode_validation_error(e)]

        removed_pcode_errors = (
            len(filtered_erros) != len(erros)
            or len(filtered_erros_raw) != len(erros_raw)
            or len(filtered_erros_formatados) != len(erros_formatados)
        )

        if not removed_pcode_errors:
            sanitized.append(perna)
            continue

        cleaned = dict(perna)
        cleaned["erros"] = filtered_erros
        cleaned["erros_raw"] = filtered_erros_raw
        cleaned["erros_formatados"] = filtered_erros_formatados

        only_pcode_errors = bool(all_errors) and all(_is_pcode_validation_error(msg) for msg in all_errors)
        if only_pcode_errors and cleaned.get("validacao_executada"):
            cleaned["aprovado"] = True
            cleaned["status"] = "APROVADO"

        sanitized.append(cleaned)

    return sanitized


def _build_effective_forbidden_steps(rule: dict, required_chain: List[dict], teste_id: str = "") -> List[dict]:
    """Monta forbidden_steps efetivos (configurados + regras automáticas)."""
    steps: List[dict] = []

    configured = rule.get("forbidden_steps") or []
    if isinstance(configured, list):
        for ref in configured:
            if isinstance(ref, dict):
                steps.append(dict(ref))

    has_0200 = any(str((step or {}).get("mti") or "") == "0200" for step in (required_chain or []))

    expects_940600 = False
    for step in (required_chain or []):
        if str((step or {}).get("de03") or "") == "940600":
            expects_940600 = True
            break
        any_de03 = (step or {}).get("any_de03")
        if isinstance(any_de03, list) and any(str(x) == "940600" for x in any_de03):
            expects_940600 = True
            break

    auto_forbid_940600 = bool(rule.get("auto_forbid_940600_on_purchase", True))
    if auto_forbid_940600 and has_0200 and not expects_940600:
        already_has = any(
            str(s.get("de03") or "") == "940600"
            and set(str(x) for x in (s.get("any_mti") or [])) == {"9600", "9610"}
            for s in steps
            if isinstance(s, dict)
        )
        if not already_has:
            steps.append(
                {
                    "label": "Fluxo 940600 indica cartão (não PCT)",
                    "any_mti": ["9600", "9610"],
                    "de03": "940600",
                }
            )

    return steps


def _extrair_stan_original_de90(perna: dict) -> Optional[str]:
    """
    Extrai o STAN original (6 dígitos) do DE90.
    Formato esperado do DE90: MTI(4) + STAN(6) + ...
    """
    bits = perna.get("bits") or {}
    de90_raw = str(bits.get("90") or bits.get(90) or "")
    if not de90_raw:
        return None

    de90_digits = "".join(ch for ch in de90_raw if ch.isdigit())
    if len(de90_digits) < 10:
        return None

    stan = de90_digits[4:10]
    return stan if len(stan) == 6 and stan.isdigit() else None


def _listar_transacoes_resultado(resultado_log: dict) -> List[dict]:
    transacoes: List[dict] = []
    if resultado_log.get("transacao_selecionada"):
        transacoes.append(resultado_log["transacao_selecionada"])
    transacoes.extend(resultado_log.get("transacoes") or [])
    return transacoes


def _expandir_pernas_relacionadas_por_de90(
    transacao_alvo: dict,
    transacoes_no_resultado: List[dict],
    de41_alvo: str,
    *,
    incluir_reverso: bool = False,
    incluir_0400_original: bool = True,
    incluir_0420_original: bool = False,
) -> List[dict]:
    """Expande pernas incluindo transacoes relacionadas por DE90 (STAN original)."""

    def _pernas_tx(tx: dict) -> List[dict]:
        return list(tx.get("pernas_todas") or tx.get("pernas") or [])

    def _tx_key(tx: dict) -> Tuple[str, str]:
        return (str(tx.get("de11") or ""), str(tx.get("de41") or ""))

    de41_ref = str(de41_alvo or "")
    pernas_expandidas: List[dict] = sorted(
        _pernas_tx(transacao_alvo),
        key=lambda x: x.get("header_line") or 0,
    )

    known_leg_keys: Set[Tuple[Any, Any, Any, Any]] = set()
    for p in pernas_expandidas:
        known_leg_keys.add((p.get("header_line"), p.get("mti"), p.get("de11"), p.get("de41")))

    included_tx_keys: Set[Tuple[str, str]] = {_tx_key(transacao_alvo)}
    fila: List[dict] = [transacao_alvo]

    def _de41_ok(tx: dict) -> bool:
        tx_de41 = str(tx.get("de41") or "")
        if not de41_ref:
            return True
        if not tx_de41:
            return True
        return tx_de41 == de41_ref

    def _adicionar_tx(tx: dict) -> None:
        k = _tx_key(tx)
        if k in included_tx_keys:
            return
        included_tx_keys.add(k)
        fila.append(tx)
        for perna_rel in _pernas_tx(tx):
            pk = (perna_rel.get("header_line"), perna_rel.get("mti"), perna_rel.get("de11"), perna_rel.get("de41"))
            if pk in known_leg_keys:
                continue
            known_leg_keys.add(pk)
            pernas_expandidas.append(perna_rel)

    while fila:
        tx_atual = fila.pop(0)
        de11_atual = str(tx_atual.get("de11") or "")

        # Direcao 1: cancelamento/desfazimento (0400/0420) -> transacao original (DE90/STAN).
        mtis_direcao_1: Set[str] = set()
        if incluir_0400_original:
            mtis_direcao_1.add("0400")
        if incluir_0420_original:
            mtis_direcao_1.add("0420")

        for p in _pernas_tx(tx_atual):
            if str(p.get("mti") or "") not in mtis_direcao_1:
                continue
            stan_original = _extrair_stan_original_de90(p)
            if not stan_original:
                continue

            for tx in transacoes_no_resultado:
                if str(tx.get("de11") or "") != stan_original:
                    continue
                if not _de41_ok(tx):
                    continue
                _adicionar_tx(tx)

        # Direcao 2 (teste 14): compra (0200) -> cancelamentos que referenciam a compra via DE90.
        if incluir_reverso and de11_atual:
            for tx in transacoes_no_resultado:
                if not _de41_ok(tx):
                    continue
                if _tx_key(tx) in included_tx_keys:
                    continue

                for p in _pernas_tx(tx):
                    if str(p.get("mti") or "") != "0400":
                        continue
                    if _extrair_stan_original_de90(p) == de11_atual:
                        _adicionar_tx(tx)
                        break

    return sorted(pernas_expandidas, key=lambda x: x.get("header_line") or 0)


def _avaliar_teste_homologacao(resultado_log: dict, de11: str, de41: str, teste_cfg: dict) -> dict:
    erros: List[str] = []
    teste_id = str(teste_cfg.get("id") or "00").zfill(2)
    chave_teste = f"teste_{int(teste_id)}" if teste_id.isdigit() else "teste"
    objetivo = str(teste_cfg.get("objetivo_esperado") or "")
    rule = teste_cfg.get("rule") or {}
    presence_only_required_chain = bool(rule.get("presence_only_required_chain", False))

    transacao_alvo = _buscar_transacao_por_chave(resultado_log, de11=de11, de41=de41)
    if transacao_alvo is None:
        erros.append("Transação com DE11/DE41 informados não foi localizada no log.")
        campos_correspondentes_aprovado = False
        teste_aprovado = False
        return {
            "aprovado": teste_aprovado,
            "status": "APROVADO" if teste_aprovado else "REPROVADO",
            "objetivo_esperado": objetivo,
            "mtis_encontrados": [],
            "resultados": {
                "campos_correspondentes": {
                    "status": "APROVADO" if campos_correspondentes_aprovado else "NEGADO",
                    "aprovado": campos_correspondentes_aprovado,
                    "texto": "Campos correspondentes Presentes aprovado" if campos_correspondentes_aprovado else "Campos correspondentes Negado",
                },
                chave_teste: {
                    "status": "APROVADO" if teste_aprovado else "NEGADO",
                    "aprovado": teste_aprovado,
                    "texto": f"Teste {teste_id} Aprovado" if teste_aprovado else f"Teste {teste_id} Negado",
                }
            },
            "erros": erros,
        }

    mtis_encontrados = _coletar_mtis_da_transacao(transacao_alvo)

    transacoes_no_resultado = _listar_transacoes_resultado(resultado_log)
    de41_alvo = str(transacao_alvo.get("de41") or de41 or "")
    pernas = _expandir_pernas_relacionadas_por_de90(
        transacao_alvo,
        transacoes_no_resultado,
        de41_alvo,
        incluir_reverso=(teste_id in {"14", "20"}),
        incluir_0400_original=(teste_id in {"14", "20"}),
        incluir_0420_original=(teste_id in {"15", "16"}),
    )

    roteiro = load_roteiro()
    required_chain = rule.get("required_chain") or []
    pernas = _sanitize_reversal_pcode_validation(pernas, required_chain)
    comparacoes = rule.get("comparacoes") or []
    any_of_conditions = rule.get("any_of_conditions") or []
    tipo_cfg = rule.get("tipo_por_id283") or {}
    forbidden_steps = _build_effective_forbidden_steps(rule, required_chain, teste_id=teste_id)
    validate_only_when_has_mti = str(rule.get("validate_only_when_has_mti") or "").strip()
    restrict_campos_to_required_chain = bool(rule.get("restrict_campos_to_required_chain", False))
    ignore_leg_status_refs = _build_ignore_leg_status_refs(rule, required_chain, teste_id=teste_id)
    ignore_leg_campos_refs = _build_ignore_leg_campos_refs(rule)

    def _leg_ignorada_status(perna: dict) -> bool:
        if not isinstance(ignore_leg_status_refs, list) or not ignore_leg_status_refs:
            return False
        return any(_step_matches(perna, ref) for ref in ignore_leg_status_refs if isinstance(ref, dict))

    def _leg_ignorada_campos(perna: dict) -> bool:
        if not isinstance(ignore_leg_campos_refs, list) or not ignore_leg_campos_refs:
            return False
        return any(_step_matches(perna, ref) for ref in ignore_leg_campos_refs if isinstance(ref, dict))

    # MTIs cobertos por cenarios do roteiro (field mti nas condicoes do scenario.when)
    scenario_mtis: Set[str] = set()
    for sc in (roteiro.get("scenarios") or []):
        for cond in (sc.get("when") or []):
            if cond.get("field") != "mti":
                continue
            if "equals" in cond and cond.get("equals") is not None:
                scenario_mtis.add(str(cond.get("equals")))
            one_of = cond.get("one_of")
            if isinstance(one_of, list):
                for m in one_of:
                    scenario_mtis.add(str(m))

    # Pernas explicitamente referenciadas no teste (cadeia/comparacoes/tipo).
    explicit_leg_indexes: Set[int] = set()
    for step in required_chain:
        for i, p in enumerate(pernas):
            if _step_matches(p, step):
                explicit_leg_indexes.add(i)

    for comp in comparacoes:
        left_ref = comp.get("left") or {}
        right_ref = comp.get("right") or {}
        for i, p in enumerate(pernas):
            if _step_matches(p, left_ref) or _step_matches(p, right_ref):
                explicit_leg_indexes.add(i)

    expected_tipo_raw = str(tipo_cfg.get("expected") or "").strip().lower()
    expected_tipo_cfg = expected_tipo_raw if expected_tipo_raw in {"credito", "debito"} else None
    # Importante: validacao de tipo (ID 253/283) NAO deve forcar validacao de bits obrigatorios
    # da perna 9600/940600. Essa perna entra apenas na regra especifica de tipo mais abaixo.
    tipo_reprove_mode_cfg = str(tipo_cfg.get("reprove_mode") or "strict").strip().lower()
    tipo_target_campos_bits = None
    if tipo_cfg and tipo_reprove_mode_cfg == "mismatch_only":
        tipo_target_campos_bits = {"mti": "9600", "de03": "940600"}

    def _leg_deve_contar_campos_bits(idx: int, perna: dict) -> bool:
        if _leg_ignorada_campos(perna):
            return False
        if tipo_target_campos_bits and _step_matches(perna, tipo_target_campos_bits):
            return False
        if restrict_campos_to_required_chain:
            return idx in explicit_leg_indexes
        mti = str(perna.get("mti") or "")
        return (idx in explicit_leg_indexes) or (mti in scenario_mtis)

    require_campos = bool(rule.get("require_campos_correspondentes", True))
    if require_campos and validate_only_when_has_mti:
        has_trigger_mti = any(str(p.get("mti") or "") == validate_only_when_has_mti for p in pernas)
        if not has_trigger_mti:
            require_campos = False
    if require_campos:
        pernas_consideradas = [
            p for i, p in enumerate(pernas)
            if _leg_deve_contar_campos_bits(i, p)
        ]
        pernas_consideradas_validadas = [p for p in pernas_consideradas if p.get("validacao_executada")]
        pernas_sem_validacao = [p for p in pernas_consideradas if not p.get("validacao_executada")]
        campos_correspondentes_aprovado = (
            (len(pernas_sem_validacao) == 0)
            and all(bool(p.get("aprovado") is True) for p in pernas_consideradas_validadas)
        )
    else:
        pernas_consideradas = []
        pernas_sem_validacao = []
        campos_correspondentes_aprovado = True

    if not campos_correspondentes_aprovado:
        erros.append("Campos/bits obrigatórios da transação não passaram na validação.")
        detalhes_campos_bits: List[str] = []
        seen: Set[str] = set()

        for perna in pernas_sem_validacao:
            mti = str(perna.get("mti") or "?")
            de03 = str(perna.get("de03") or "?")
            hdr = perna.get("header_line")
            detalhe = (
                f"Perna MTI={mti} DE03={de03}" + (f" (linha {hdr})" if hdr else "")
                + ": validação individual não executada; não foi possível validar bits obrigatórios."
            )
            if detalhe not in seen:
                seen.add(detalhe)
                detalhes_campos_bits.append(detalhe)

        for i, perna in enumerate(pernas):
            if not _leg_deve_contar_campos_bits(i, perna):
                continue
            perna_erros = perna.get("erros") or []
            if not perna_erros:
                continue

            mti = str(perna.get("mti") or "?")
            de03 = str(perna.get("de03") or "?")
            hdr = perna.get("header_line")
            prefix = f"Perna MTI={mti} DE03={de03}" + (f" (linha {hdr})" if hdr else "")

            for e in perna_erros:
                msg = str(e)
                # Foco nos motivos de campos/bits obrigatorios e estrutura dos dados.
                if (
                    ("Bits obrigatórios ausentes" in msg)
                    or ("Bit 47: sub-IDs obrigatórios ausentes" in msg)
                    or ("Bit 47/ID" in msg)
                    or ("DE47/ID238" in msg)
                ):
                    detalhe = f"{prefix}: {msg}"
                    if detalhe not in seen:
                        seen.add(detalhe)
                        detalhes_campos_bits.append(detalhe)

        if detalhes_campos_bits:
            erros.extend(detalhes_campos_bits)
        else:
            erros.append(
                "Não foi possível identificar no detalhe quais campos/bits falharam; verifique os erros por perna na grade."
            )

    _, chain_errors = _find_chain_indexes(pernas, required_chain)
    erros.extend(chain_errors)

    forbidden_seen: Set[str] = set()
    for p in pernas:
        if _leg_ignorada_campos(p):
            continue
        for step in forbidden_steps:
            if not isinstance(step, dict):
                continue
            if not _step_matches(p, step):
                continue
            lbl = str(step.get("label") or "perna proibida")
            mti = str(p.get("mti") or "?")
            de03 = str(p.get("de03") or "?")
            step_bit47_ne = step.get("bit47_ne") or {}
            step_de03_ne = step.get("de03_ne")
            
            if step_bit47_ne and isinstance(step_bit47_ne, dict):
                recebidos = []
                for id_tag in step_bit47_ne:
                    atual_val = _extrair_id47_da_perna(p, str(id_tag))
                    recebidos.append(atual_val or "(vazio)")
                msg = f"{lbl}; recebido: {', '.join(recebidos)}."
            elif step_de03_ne:
                msg = f"{lbl}; recebido: {de03}."
            elif "de03" in step:
                msg = f"{lbl}; recebido: {de03}."
            else:
                msg = f"{lbl} (MTI={mti} DE03={de03})."
            if msg not in forbidden_seen:
                forbidden_seen.add(msg)
                erros.append(msg)
            break

    require_pernas_completas = bool(rule.get("require_pernas_completas", True))
    if require_pernas_completas:
        erros.extend(_avaliar_cadeias_completas_transacao(pernas))

    erros.extend(_avaliar_comparacoes(pernas, comparacoes))
    erros.extend(_avaliar_any_of_conditions(pernas, any_of_conditions))

    tipo_info = None
    if tipo_cfg:
        target_cfg = dict(tipo_cfg.get("target") or {})
        tipo_reprove_mode = tipo_reprove_mode_cfg
        if not target_cfg:
            target_cfg = {"mti": "9600", "de03": "940600"}

        target_idx = next((i for i, p in enumerate(pernas) if _step_matches(p, target_cfg)), None)
        versao_bit61 = _extrair_versao_bit61_transacao(pernas)
        versao_num = _parse_versao_bit61(versao_bit61 or "")

        source_kind = str(tipo_cfg.get("source") or "id253_283_by_bit61").strip().lower()
        # Fonte padrão:
        # - versao <= 10.44  -> usa ID 253
        # - versao >= 10.45  -> usa ID 283
        id_fonte = "283"
        source_is_text = False
        if source_kind == "bit48_id506_after_second_at":
            id_fonte = "506"
        elif source_kind == "bit48_id506":
            id_fonte = "506"
        elif source_kind == "bit62_id505":
            id_fonte = "505"
        elif source_kind == "bit62_text_from_id505":
            id_fonte = "505"
            source_is_text = True
        elif source_kind == "bit62_text_after_second_at":
            id_fonte = "62_text"
            source_is_text = True
        elif source_kind == "bit48_text_after_second_at":
            id_fonte = "48_text"
            source_is_text = True
        elif versao_num is not None and versao_num <= (10, 44):
            id_fonte = "253"

        id_val = ""
        id505_val = ""
        id506_val = ""
        tipo_detectado = None
        expected_tipo = expected_tipo_cfg
        mapa = tipo_cfg.get("prefix_map") or {"01": "credito", "02": "debito"}

        if target_idx is not None:
            id505_val = _extrair_id505_bit62(pernas[target_idx])
            id506_val = _extrair_id506_bit48(pernas[target_idx])
            if id_fonte == "253":
                id_val = _extrair_id47_da_perna(pernas[target_idx], "253")
            elif id_fonte == "505":
                if source_is_text:
                    id_val = _extrair_texto_id505_bit62(pernas[target_idx])
                else:
                    id_val = id505_val
            elif id_fonte == "506":
                if source_kind == "bit48_id506_after_second_at":
                    id_val = _extrair_id506_bit48_apos_segundo_arroba(pernas[target_idx])
                else:
                    id_val = id506_val
            elif id_fonte == "48_text":
                id_val = _extrair_texto_bit48_apos_segundo_arroba(pernas[target_idx])
            elif id_fonte == "62_text":
                id_val = _extrair_texto_bit62_apos_segundo_arroba(pernas[target_idx])
                if not str(id_val or "").strip():
                    id_val = _extrair_texto_id505_bit62(pernas[target_idx])
                if not str(id_val or "").strip():
                    id_val = _extrair_id506_bit48_apos_segundo_arroba(pernas[target_idx])
            else:
                id_val = _extrair_id283_da_perna(pernas[target_idx])
            if source_is_text or id_fonte in {"48_text", "62_text"}:
                tipo_detectado = _tipo_por_texto_bit48(id_val)
            else:
                # Para 253/283, prioriza leitura por TAG 01 no formato compacto TAG/VALOR.
                if id_fonte in {"253", "283"}:
                    tipo_detectado = _tipo_por_tag01_compacto(mapa, id_val) or _tipo_por_prefixo(mapa, id_val)
                else:
                    tipo_detectado = _tipo_por_prefixo(mapa, id_val)

        fonte_tipo_desc = _descricao_fonte_tipo(source_kind, id_fonte)

        if expected_tipo:
            if tipo_reprove_mode == "mismatch_only":
                if (target_idx is not None) and (tipo_detectado is not None) and (tipo_detectado != str(expected_tipo)):
                    erros.append(
                        f"Tipo divergente via {fonte_tipo_desc}: esperado '{expected_tipo}', detectado '{tipo_detectado}' "
                        f"(valor lido={id_val}) na perna 9600 pcode 940600 (versão Bit 61={versao_bit61 or 'N/D'})."
                    )
            else:
                if target_idx is None:
                    erros.append(
                        f"Perna alvo para validar tipo via {fonte_tipo_desc} não foi encontrada na cadeia."
                    )
                elif tipo_detectado is None:
                    erros.append(
                        f"Não foi possível determinar débito/crédito via {fonte_tipo_desc} "
                        f"na perna alvo (versão Bit 61={versao_bit61 or 'N/D'})."
                    )
                elif tipo_detectado != str(expected_tipo):
                    erros.append(
                        f"Tipo divergente via {fonte_tipo_desc}: esperado '{expected_tipo}', detectado '{tipo_detectado}' "
                        f"(valor lido={id_val}) na perna alvo (versão Bit 61={versao_bit61 or 'N/D'})."
                    )

        tipo_info = {
            "esperado": expected_tipo,
            "detectado": tipo_detectado,
            "reprove_mode": tipo_reprove_mode,
            "versao_bit61": versao_bit61,
            "perna_alvo": f"{str(target_cfg.get('mti') or '')}_{str(target_cfg.get('de03') or '')}".strip("_"),
            "source": source_kind,
            "source_desc": fonte_tipo_desc,
            "id_fonte": id_fonte,
            "id_valor": id_val,
            "id253": (id_val if id_fonte == "253" else ""),
            "id283": (id_val if id_fonte == "283" else ""),
            "id505": id505_val,
            "id506": id506_val,
            "cupom_via_cliente": id505_val,
            "cupom_via_loja": id506_val,
        }

    teste_aprovado = campos_correspondentes_aprovado and len(erros) == 0
    return {
        "aprovado": teste_aprovado,
        "status": "APROVADO" if teste_aprovado else "REPROVADO",
        "objetivo_esperado": objetivo,
        "mtis_encontrados": mtis_encontrados,
        "tipo_9610_940600": tipo_info,
        "resultados": {
            "campos_correspondentes": {
                "status": "APROVADO" if campos_correspondentes_aprovado else "NEGADO",
                "aprovado": campos_correspondentes_aprovado,
                "texto": "Campos correspondentes Presentes aprovado" if campos_correspondentes_aprovado else "Campos correspondentes Negado",
            },
            chave_teste: {
                "status": "APROVADO" if teste_aprovado else "NEGADO",
                "aprovado": teste_aprovado,
                "texto": f"Teste {teste_id} Aprovado" if teste_aprovado else f"Teste {teste_id} Negado",
            }
        },
        "erros": erros,
    }


def _label_from_step(step: dict, fallback_idx: int) -> str:
    label = str(step.get("label") or "").strip()
    if label:
        return label

    mti = str(step.get("mti") or "").strip()
    de03 = str(step.get("de03") or "").strip()
    if mti and de03:
        return f"{mti} pcode {de03}"
    if mti:
        return mti

    any_mti = step.get("any_mti")
    if isinstance(any_mti, list) and any_mti:
        mtis = "/".join(str(x) for x in any_mti)
        return f"{mtis} pcode {de03}" if de03 else mtis

    return f"Passo {fallback_idx}"


def _avaliar_passos_objetivo(
    pernas: List[dict],
    required_chain: List[dict],
    presence_only_required_chain: bool = False,
) -> Tuple[List[dict], Set[int]]:
    resultados: List[dict] = []
    usados: Set[int] = set()
    search_from = 0

    for idx_step, step in enumerate(required_chain, start=1):
        found = None
        for i in range(search_from, len(pernas)):
            if _step_matches(pernas[i], step):
                found = i
                break

        label = _label_from_step(step, idx_step)
        if found is None:
            if bool(step.get("optional", False)):
                resultados.append({
                    "ordem": idx_step,
                    "label": label,
                    "aprovado": None,
                    "status": "Não Aplica",
                    "motivo": f"Passo opcional não encontrado no log: {label}",
                    "perna_idx": None,
                })
                continue
            resultados.append({
                "ordem": idx_step,
                "label": label,
                "aprovado": False,
                "status": "NEGADO",
                "motivo": f"Passo esperado não encontrado no log: {label}",
                "perna_idx": None,
            })
            continue

        search_from = found + 1
        usados.add(found)
        perna = pernas[found]
        perna_ok = bool(perna.get("aprovado") is True)
        perna_erros = perna.get("erros") or []
        if perna_ok:
            motivo = f"Passo encontrado e perna validada: {label}"
            status = "APROVADO"
        else:
            detalhe = "; ".join(str(x) for x in perna_erros[:3]) if perna_erros else "sem detalhe"
            motivo = f"Passo encontrado, porém a perna reprovou validação: {detalhe}"
            status = "NEGADO"

        resultados.append({
            "ordem": idx_step,
            "label": label,
            "aprovado": perna_ok,
            "status": status,
            "motivo": motivo,
            "perna_idx": int(found),
        })

    return resultados, usados


def avaliar_teste_homologacao_web(
    conteudo_log: str,
    teste_id: str,
    cliente: str = "LOCAL",
    debug: bool = False,
    de11: Optional[str] = None,
    de41: Optional[str] = None,
) -> dict:
    """
    Avalia um log completo para um teste de homologação e retorna
    uma visão por perna orientada ao front-end.
    Opcionalmente filtra por DE11/DE41 para encontrar a TRN desejada.
    """
    roteiro = load_roteiro()
    homolog_tests = _get_homolog_tests(roteiro)
    tid = str(teste_id).zfill(2)
    if tid not in homolog_tests:
        raise ValueError(f"Teste inválido: {teste_id}")

    teste_cfg = homolog_tests[tid]
    objetivo = str(teste_cfg.get("objetivo_esperado") or "")
    rule = teste_cfg.get("rule") or {}
    required_chain = rule.get("required_chain") or []
    comparacoes = rule.get("comparacoes") or []
    forbidden_steps = _build_effective_forbidden_steps(rule, required_chain, teste_id=tid)
    tipo_cfg = rule.get("tipo_por_id283") or {}
    presence_only_required_chain = bool(rule.get("presence_only_required_chain", False))
    ignore_leg_status_refs = _build_ignore_leg_status_refs(rule, required_chain, teste_id=tid)
    ignore_leg_campos_refs = _build_ignore_leg_campos_refs(rule)
    validate_only_when_has_mti_web = str(rule.get("validate_only_when_has_mti") or "").strip()
    restrict_campos_to_required_chain_web = bool(rule.get("restrict_campos_to_required_chain", False))

    resultado_log_full = validar_log_iso_formatado(
        conteudo_log,
        cliente=cliente,
        debug=debug,
        apenas_pernas_interesse=False,
    )

    resultado_log_view = validar_log_iso_formatado(
        conteudo_log,
        cliente=cliente,
        debug=debug,
        filtro_de11=(de11 or None),
        filtro_de41=(de41 or None),
        apenas_pernas_interesse=False,
    )
    validacao_teste = _avaliar_teste_homologacao(
        resultado_log_full,
        de11=(de11 or ""),
        de41=(de41 or ""),
        teste_cfg=teste_cfg,
    )

    transacoes: List[dict] = []
    if resultado_log_view.get("transacao_selecionada"):
        transacoes.append(resultado_log_view["transacao_selecionada"])
    transacoes.extend(resultado_log_view.get("transacoes") or [])

    pernas: List[dict] = []
    de11_ref = str(de11 or "")
    de41_ref = str(de41 or "")
    transacao_alvo_full = _buscar_transacao_por_chave(resultado_log_full, de11=de11_ref, de41=de41_ref)

    if transacao_alvo_full is not None:
        pernas = _expandir_pernas_relacionadas_por_de90(
            transacao_alvo_full,
            _listar_transacoes_resultado(resultado_log_full),
            str(transacao_alvo_full.get("de41") or de41_ref or ""),
            incluir_reverso=(tid in {"14", "20"}),
            incluir_0400_original=(tid in {"14", "20"}),
            incluir_0420_original=(tid in {"15", "16"}),
        )
    else:
        for t in transacoes:
            pernas.extend(t.get("pernas_todas") or t.get("pernas") or [])
        pernas = sorted(pernas, key=lambda x: x.get("header_line") or 0)

    pernas = _sanitize_reversal_pcode_validation(pernas, required_chain)

    def _leg_ignorada_status(perna: dict) -> bool:
        if not isinstance(ignore_leg_status_refs, list) or not ignore_leg_status_refs:
            return False
        return any(_step_matches(perna, ref) for ref in ignore_leg_status_refs if isinstance(ref, dict))

    def _leg_ignorada_campos(perna: dict) -> bool:
        if not isinstance(ignore_leg_campos_refs, list) or not ignore_leg_campos_refs:
            return False
        return any(_step_matches(perna, ref) for ref in ignore_leg_campos_refs if isinstance(ref, dict))

    has_trigger_mti_web = True
    if validate_only_when_has_mti_web:
        has_trigger_mti_web = any(str(p.get("mti") or "") == validate_only_when_has_mti_web for p in pernas)

    explicit_leg_indexes_web: Set[int] = set()
    if restrict_campos_to_required_chain_web and has_trigger_mti_web:
        _sf = 0
        for _st in required_chain:
            for _ip in range(_sf, len(pernas)):
                if _step_matches(pernas[_ip], _st) and not _leg_ignorada_campos(pernas[_ip]):
                    explicit_leg_indexes_web.add(_ip)
                    _sf = _ip + 1
                    break

    def _deve_avaliar_dados_perna(idx: int, perna: dict) -> bool:
        if not has_trigger_mti_web:
            return False
        if restrict_campos_to_required_chain_web and idx not in explicit_leg_indexes_web:
            return False
        return True

    passos, perna_indexes_objetivo = _avaliar_passos_objetivo(
        pernas,
        required_chain,
        presence_only_required_chain=presence_only_required_chain,
    )

    tipo_target_step = dict(tipo_cfg.get("target") or {}) if tipo_cfg else {}
    tipo_target_idx = (
        next((i for i, p in enumerate(pernas) if _step_matches(p, tipo_target_step)), None)
        if tipo_target_step else None
    )

    # Aplica ignore_leg_campos_bits aos passos objetivo
    for s in passos:
        idx = s.get("perna_idx")
        if idx is not None and 0 <= idx < len(pernas):
            # Não aplicar ignore se for tipo_target (para preservar validação de tipo)
            if _leg_ignorada_campos(pernas[idx]) and not (tipo_target_idx is not None and idx == int(tipo_target_idx)):
                s["aprovado"] = True
                s["status"] = "APROVADO"
                s["motivo"] = "Passo encontrado e aprovado por presença da perna (sem validação de bits/IDs)."

    def _step_has_expected_mti(step: dict, perna: dict) -> bool:
        mti_perna = str(perna.get("mti") or "")
        mti_step = str(step.get("mti") or "")
        if mti_step and mti_perna == mti_step:
            return True
        any_mti = step.get("any_mti")
        if isinstance(any_mti, list) and any_mti:
            return mti_perna in {str(x) for x in any_mti}
        return False

    pernas_transacao_buscada = []
    transacao_selecionada = resultado_log_view.get("transacao_selecionada") or {}
    if isinstance(transacao_selecionada, dict):
        pernas_transacao_buscada = list(
            transacao_selecionada.get("pernas_todas") or transacao_selecionada.get("pernas") or []
        )

    filtro_transacao_informado = bool((de11 or "").strip() or (de41 or "").strip())
    avaliar_pernas_referencia = pernas_transacao_buscada if (filtro_transacao_informado and pernas_transacao_buscada) else pernas
    has_objetivo_na_transacao = any(
        _step_matches(perna_ref, step)
        for perna_ref in avaliar_pernas_referencia
        for step in required_chain
        if isinstance(step, dict)
    )
    has_mti_objetivo_na_transacao = any(
        _step_has_expected_mti(step, perna_ref)
        for perna_ref in avaliar_pernas_referencia
        for step in required_chain
        if isinstance(step, dict)
    )
    skip_validation_outside_objective = bool(required_chain) and (not has_objetivo_na_transacao) and (not has_mti_objetivo_na_transacao)

    if skip_validation_outside_objective:
        for s in passos:
            s["aprovado"] = False
            s["status"] = "NEGADO"
            s["motivo"] = (
                "Transação buscada não pertence ao objetivo esperado do teste; validação de pernas não aplicada."
            )
            s["perna_idx"] = None
        perna_indexes_objetivo = set()

    tipo_info = validacao_teste.get("tipo_9610_940600") or {}
    tipo_mode = str(tipo_info.get("reprove_mode") or tipo_cfg.get("reprove_mode") or "strict").strip().lower()

    forbidden_indexes: Set[int] = set()
    forbidden_motivos: Dict[int, str] = {}
    for i, p in enumerate(pernas):
        if _leg_ignorada_campos(p):
            continue
        for step in forbidden_steps:
            if not isinstance(step, dict):
                continue
            if _step_matches(p, step):
                forbidden_indexes.add(i)
                lbl = str(step.get("label") or "regra de reprovação")
                mti = str(p.get("mti") or "")
                de03_atual = str(p.get("de03") or "")
                step_bit47_ne = step.get("bit47_ne") or {}
                step_de03_ne = step.get("de03_ne")
                
                if step_bit47_ne and isinstance(step_bit47_ne, dict):
                    recebidos = []
                    for id_tag in step_bit47_ne:
                        atual_val = _extrair_id47_da_perna(p, str(id_tag))
                        recebidos.append(atual_val or "(vazio)")
                    forbidden_motivos[i] = f"{lbl}; recebido: {', '.join(recebidos)}."
                elif step_de03_ne:
                    forbidden_motivos[i] = f"{lbl}; recebido: {de03_atual}."
                elif "de03" in step:
                    forbidden_motivos[i] = f"{lbl}; recebido: {de03_atual}."
                else:
                    forbidden_motivos[i] = f"{lbl}."
                break

    comparison_failed_indexes: Set[int] = set()
    comparison_failed_reason_by_index: Dict[int, str] = {}
    for comp in comparacoes:
        if not isinstance(comp, dict):
            continue
        label = str(comp.get("label") or "comparacao")
        op = str(comp.get("operator") or "==")
        left_ref = comp.get("left") or {}
        right_ref = comp.get("right") or {}

        left_idx = _find_matching_step_index(pernas, left_ref)
        right_idx = _find_matching_step_index(pernas, right_ref)
        if left_idx is None or right_idx is None:
            continue

        left_val = _extrair_valor_ref(pernas[left_idx], left_ref)
        right_val = _extrair_valor_ref(pernas[right_idx], right_ref)
        if left_val == "" or right_val == "":
            msg = f"Falha em comparação obrigatória '{label}': valor LEFT/RIGHT ausente."
            for idx_fail in (int(left_idx), int(right_idx)):
                comparison_failed_indexes.add(idx_fail)
                comparison_failed_reason_by_index[idx_fail] = msg
            continue

        ok = True
        if op == "==":
            ok = left_val == right_val
        elif op == "!=":
            ok = left_val != right_val
        elif op in {"<", ">", "<=", ">="}:
            if left_val.isdigit() and right_val.isdigit():
                li = int(left_val)
                ri = int(right_val)
                if op == "<":
                    ok = li < ri
                elif op == ">":
                    ok = li > ri
                elif op == "<=":
                    ok = li <= ri
                else:
                    ok = li >= ri
            else:
                ok = False
        else:
            ok = False

        if not ok:
            msg = (
                f"Falha em comparação obrigatória '{label}': LEFT='{left_val}' {op} RIGHT='{right_val}'."
            )
            for idx_fail in (int(left_idx), int(right_idx)):
                comparison_failed_indexes.add(idx_fail)
                comparison_failed_reason_by_index[idx_fail] = msg

    # Sincroniza falhas de comparação vindas da validação global (escopo completo)
    # para a grade filtrada do front-end.
    erros_globais_teste = [str(e) for e in (validacao_teste.get("erros") or [])]
    for comp in comparacoes:
        if not isinstance(comp, dict):
            continue
        label = str(comp.get("label") or "")
        if not label:
            continue
        msg_match = next((e for e in erros_globais_teste if f"Comparação '{label}'" in e), None)
        if not msg_match:
            continue

        left_ref = comp.get("left") or {}
        right_ref = comp.get("right") or {}
        for i, p in enumerate(pernas):
            if _step_matches(p, left_ref) or _step_matches(p, right_ref):
                comparison_failed_indexes.add(int(i))
                comparison_failed_reason_by_index[int(i)] = msg_match

    for s in passos:
        idx = s.get("perna_idx")
        if idx is None:
            continue
        if idx < 0 or idx >= len(pernas):
            continue
        if _leg_ignorada_campos(pernas[idx]):
            s["aprovado"] = True
            s["status"] = "APROVADO"
            s["motivo"] = "Passo encontrado e aprovado por presença da perna (sem validação de bits/IDs)."

    pernas_saida: List[dict] = []
    for i, p in enumerate(pernas):
        refs = [s for s in passos if s.get("perna_idx") == i]
        is_tipo_target = (tipo_target_idx is not None and i == int(tipo_target_idx))
        if is_tipo_target:
            fonte_desc = str(tipo_info.get("source_desc") or _descricao_fonte_tipo(str(tipo_info.get("source") or ""), str(tipo_info.get("id_fonte") or "")))
            refs.append({"label": f"Validação tipo débito/crédito ({fonte_desc})", "perna_idx": i})

        is_objetivo = (i in perna_indexes_objetivo) or is_tipo_target
        perna_aprovado = p.get("aprovado")
        erros_perna = list(p.get("erros") or [])
        mti = str(p.get("mti") or "")
        de03 = str(p.get("de03") or "")
        bit04 = str((p.get("bits") or {}).get("04") or "")

        if skip_validation_outside_objective:
            status = "Não Aplica"
            aprovado = None
            motivo = "Perna fora do objetivo esperado para o teste selecionado; validação não aplicada."
        elif i in forbidden_indexes:
            status = "REPROVADO"
            aprovado = False
            motivo = forbidden_motivos.get(i) or "Reprovado por regra do teste."
        elif i in comparison_failed_indexes:
            status = "REPROVADO"
            aprovado = False
            motivo = comparison_failed_reason_by_index.get(i) or "Perna reprovada por falha em comparação obrigatória."
        elif is_tipo_target:
            esperado_tipo = str(tipo_info.get("esperado") or "")
            detectado_tipo = str(tipo_info.get("detectado") or "")
            id_fonte = str(tipo_info.get("id_fonte") or "")
            fonte_desc = str(tipo_info.get("source_desc") or _descricao_fonte_tipo(str(tipo_info.get("source") or ""), id_fonte))
            if esperado_tipo and not detectado_tipo:
                status = "REPROVADO"
                aprovado = False
                motivo = (
                    f"Não foi possível determinar o tipo na perna alvo ({fonte_desc}); esperado '{esperado_tipo}'."
                )
            elif esperado_tipo and detectado_tipo and detectado_tipo != esperado_tipo:
                status = "REPROVADO"
                aprovado = False
                motivo = (
                    f"Tipo divergente ({fonte_desc}): esperado '{esperado_tipo}', detectado '{detectado_tipo}'."
                )
            else:
                status = "APROVADO"
                aprovado = True
                motivo = "Perna alvo validada para tipo de transação (débito/crédito)."
        elif _leg_ignorada_campos(p):
            status = "APROVADO"
            aprovado = True
            motivo = "Perna presente no log e configurada para não validar dados (bits/IDs) neste teste."
            erros_perna = []
        elif not _deve_avaliar_dados_perna(i, p):
            status = "Não Aplica"
            aprovado = None
            motivo = "Validação de dados não aplicável para esta perna neste teste."
        elif perna_aprovado is True:
            status = "APROVADO"
            aprovado = True
            motivo = "Perna esperada no objetivo e validada com sucesso." if is_objetivo else "Perna validada com sucesso."
        elif is_objetivo or perna_aprovado is False or erros_perna:
            status = "REPROVADO"
            aprovado = False
            detalhe = "; ".join(str(x) for x in erros_perna[:3]) if erros_perna else "sem detalhe"
            if is_objetivo:
                motivo = f"Perna esperada no objetivo, mas reprovada: {detalhe}"
            else:
                motivo = f"Perna fora do objetivo, mas reprovada: {detalhe}"
        else:
            status = "Não Aplica"
            aprovado = None
            motivo = "Perna não faz parte do objetivo esperado do teste selecionado."

        pernas_saida.append({
            "ordem_log": i + 1,
            "header_line": p.get("header_line"),
            "raw_iso_line": p.get("raw_iso_line"),
            "raw_iso": p.get("raw_iso"),
            "iso_formatado": _formatar_iso_perna(
                p.get("bits") or {},
                mti,
                bit47_map_fmt=(p.get("bit47_map_fmt") or {}),
                bit47_ids_fmt=(p.get("bit47_ids_fmt") or []),
                bit47_map_raw=(p.get("bit47_map_raw") or {}),
                bit47_ids_raw=(p.get("bit47_ids_raw") or []),
            ),
            "mti": mti,
            "de03": de03,
            "de11": p.get("de11"),
            "de41": p.get("de41"),
            "bit04": bit04,
            "cenario": p.get("cenario"),
            "bit47_origem": p.get("bit47_origem"),
            "status": status,
            "aprovado": aprovado,
            "motivo": motivo,
            "erros": [] if _leg_ignorada_campos(p) else list(p.get("erros") or []),
            "erros_raw": [] if _leg_ignorada_campos(p) else list(p.get("erros_raw") or []),
            "erros_formatados": [] if _leg_ignorada_campos(p) else list(p.get("erros_formatados") or []),
            "avisos": list(p.get("avisos") or []),
            "objetivo_refs": [r.get("label") for r in refs],
        })

    aprovado_geral = bool(validacao_teste.get("aprovado") is True) and not skip_validation_outside_objective
    motivos_status_geral = list(validacao_teste.get("erros") or [])
    if skip_validation_outside_objective:
        motivos_status_geral.insert(
            0,
            "Transação buscada não faz parte das pernas do objetivo esperado deste teste.",
        )

    return {
        "teste": {
            "id": teste_cfg.get("id"),
            "nome": teste_cfg.get("nome"),
            "descricao": teste_cfg.get("descricao"),
            "objetivo_esperado": objetivo,
        },
        "status": "APROVADO" if aprovado_geral else "REPROVADO",
        "aprovado": aprovado_geral,
        "motivos_status_geral": motivos_status_geral,
        "passos_objetivo": passos,
        "pernas": pernas_saida,
        "resumo": {
            "total_pernas": len(pernas_saida),
            "pernas_objetivo": len(perna_indexes_objetivo),
            "pernas_aprovadas": sum(1 for p in pernas_saida if p.get("aprovado") is True),
            "pernas_negadas": sum(1 for p in pernas_saida if p.get("aprovado") is False),
            "pernas_nao_aplicam": sum(1 for p in pernas_saida if p.get("aprovado") is None),
        },
        "validacao_teste": validacao_teste,
        "resultado_log": resultado_log_view,
    }


def executar_homologacao_interativa(debug: bool = False) -> dict:
    print("\n=== Fluxo de Homologação ===")
    print("1) Selecionar teste")
    print("2) Informar Bit 11 e Bit 41")
    print("3) Subir log")
    print("4) Validar")

    roteiro = load_roteiro()
    homolog_tests = _get_homolog_tests(roteiro)
    if not homolog_tests:
        raise ValueError("Roteiro sem 'homolog_tests' configurado.")

    teste_id = _selecionar_teste_homologacao(homolog_tests)
    teste_cfg = homolog_tests[teste_id]

    print("\n=== Identificação da Transação ===")
    de11, de41 = _ler_de11_de41_interativo()

    print("\n=== Upload do Log ===")
    conteudo = _ler_log_homologacao()

    resultado_log_full = validar_log_iso_formatado(
        conteudo,
        cliente="LOCAL",
        debug=debug,
        apenas_pernas_interesse=False,
    )

    resultado_log = validar_log_iso_formatado(
        conteudo,
        cliente="LOCAL",
        debug=debug,
        filtro_de11=de11,
        filtro_de41=de41,
        apenas_pernas_interesse=False,
    )

    validacao_teste = _avaliar_teste_homologacao(resultado_log_full, de11=de11, de41=de41, teste_cfg=teste_cfg)

    aprovado = bool(validacao_teste.get("aprovado"))
    return {
        "modo": "homologacao_interativa",
        "teste": {
            "id": teste_cfg.get("id"),
            "nome": teste_cfg.get("nome"),
            "descricao": teste_cfg.get("descricao"),
            "objetivo_esperado": teste_cfg.get("objetivo_esperado"),
        },
        "filtros": {
            "de11": de11,
            "de41": de41,
        },
        "status": "APROVADO" if aprovado else "REPROVADO",
        "aprovado": aprovado,
        "validacao_teste": validacao_teste,
        "resultado_log": resultado_log,
    }

#endregion

#region CLI

def _ler_entrada() -> str:
    path = None
    if "--arquivo" in sys.argv:
        i = sys.argv.index("--arquivo")
        if i + 1 < len(sys.argv):
            path = sys.argv[i + 1]
    elif "-f" in sys.argv:
        i = sys.argv.index("-f")
        if i + 1 < len(sys.argv):
            path = sys.argv[i + 1]

    if path:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    print("Cole a(s) mensagem(ns) de log abaixo. Finalize com CTRL+D (Linux/macOS) ou CTRL+Z + Enter (Windows):\n")
    return sys.stdin.read()


def _is_empty_output_value(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) == 0
    return False


def _prune_empty_output(data: Any) -> Any:
    """
    Remove recursivamente valores vazios para reduzir ruído no JSON de saída.
    Considera vazio: None, "", [], {}, () e set().
    """
    if isinstance(data, dict):
        out: Dict[Any, Any] = {}
        for k, v in data.items():
            pv = _prune_empty_output(v)
            if not _is_empty_output_value(pv):
                out[k] = pv
        return out

    if isinstance(data, list):
        out_list = []
        for item in data:
            pitem = _prune_empty_output(item)
            if not _is_empty_output_value(pitem):
                out_list.append(pitem)
        return out_list

    if isinstance(data, tuple):
        out_tuple = tuple(
            pitem
            for pitem in (_prune_empty_output(x) for x in data)
            if not _is_empty_output_value(pitem)
        )
        return out_tuple

    if isinstance(data, set):
        out_set = {
            pitem
            for pitem in (_prune_empty_output(x) for x in data)
            if not _is_empty_output_value(pitem)
        }
        return out_set

    return data

if __name__ == "__main__":
    try:
        debug = ("--debug" in sys.argv)
        modo_homologacao_interativa = (("--homolog" in sys.argv) or ("--interativo" in sys.argv))
        manter_vazios = ("--manter-vazios" in sys.argv)

        cenario_nome = None
        forcar_cartao = ("--forcar-cartao" in sys.argv)
        forcar_pct = ("--forcar-pct" in sys.argv)

        if "--cenario" in sys.argv:
            i = sys.argv.index("--cenario")
            if i + 1 < len(sys.argv):
                cenario_nome = sys.argv[i + 1].strip()

        filtro_de11 = None
        filtro_de41 = None
        if "--de11" in sys.argv:
            i = sys.argv.index("--de11")
            if i + 1 < len(sys.argv):
                filtro_de11 = sys.argv[i + 1].strip()
        if "--de41" in sys.argv:
            i = sys.argv.index("--de41")
            if i + 1 < len(sys.argv):
                filtro_de41 = sys.argv[i + 1].strip()

        apenas_pernas_interesse = ("--todas-pernas" not in sys.argv)

        modo_log_iso = ("--log-iso" in sys.argv)

        if modo_homologacao_interativa:
            resultado = executar_homologacao_interativa(debug=debug)
        else:
            conteudo = _ler_entrada()

            auto_log_iso = (
                ("ISO . FEPAS:" in conteudo)
                and re.search(r'(?m)^\s*\d{1,3}\s*\(\s*\d+\):\s*\[', conteudo) is not None
            )

            if modo_log_iso or auto_log_iso:
                resultado = validar_log_iso_formatado(
                    conteudo,
                    cliente="LOCAL",
                    debug=debug,
                    cenario_forcado=cenario_nome,
                    forcar_cartao=forcar_cartao,
                    forcar_pct=forcar_pct,
                    filtro_de11=filtro_de11,
                    filtro_de41=filtro_de41,
                    apenas_pernas_interesse=apenas_pernas_interesse,
                )
            else:
                resultado = validar_iso_0200_raw(
                    conteudo,
                    cliente="LOCAL",
                    debug=debug,
                    cenario_forcado=cenario_nome,
                    forcar_cartao=forcar_cartao,
                    forcar_pct=forcar_pct
                )
        resultado_saida = resultado if manter_vazios else _prune_empty_output(resultado)
        print(json.dumps(resultado_saida, ensure_ascii=False, indent=2))
        sys.exit(0 if resultado.get("aprovado") else 1)
    except FileNotFoundError as e:
        print(f"Arquivo não encontrado: {e}")
        sys.exit(2)
    except Exception as e:
        print(f"Erro ao validar: {e}")
        sys.exit(3)

#endregion