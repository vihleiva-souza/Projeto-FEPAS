# validador_cardse.py
"""
Validador ISO 8583 específico para Autorizador CARDSE.
Foca APENAS em mensagens recebidas da processadora (PROCESSADORA -> FEPAS).
"""

import json
import os
import re
import sys
from typing import Dict, List, Set, Tuple, Optional, Any

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROTEIRO_PATH = os.path.join(BASE_DIR, "data", "roteiros", "roteiro_iso_novo_produto.json")
DEFAULT_LOGS_DIR = os.path.join(BASE_DIR, "LOGS de TESTE")


def load_roteiro(path=ROTEIRO_PATH) -> dict:
    """Carrega o roteiro JSON do novo produto."""
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _normalize_mti(value: Any) -> str:
    """Normaliza MTI para 4 dígitos quando possível (ex.: 210 -> 0210)."""
    raw = str(value or "").strip()
    if not raw:
        return ""

    digits = re.sub(r"\D", "", raw)
    if not digits:
        return raw

    if len(digits) <= 4:
        return digits.zfill(4)

    return digits


def _normalize_numeric_text(value: Any) -> str:
    """Normaliza texto numérico removendo zeros à esquerda para comparação lógica."""
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if digits == "":
        return raw
    return str(int(digits)) if digits.isdigit() else digits


def _extract_message_fields(lines: List[str], start_idx: int) -> Tuple[Dict[str, str], int]:
    """
    Extrai campos de uma mensagem ISO 8583 a partir de um índice inicial.
    Retorna (campos_dict, next_idx) onde next_idx é a próxima linha a processar.
    """
    campos: Dict[str, str] = {}
    last_field_num: Optional[str] = None
    last_tlv_tag: Optional[str] = None
    tlv_field_num: Optional[str] = None
    tlv_data: Dict[str, str] = {}
    
    field_re = re.compile(r'^\s+(\d+)\s*\(\s*\d+\s*\):\s*\[([^\]]*)\]')
    continuation_re = re.compile(r'^\s+\[([^\]]*)\]\s*$')
    
    i = start_idx
    while i < len(lines) and not lines[i].startswith("aud"):
        line = lines[i]
        m = field_re.match(line)
        
        if m:
            # Se estava coletando TLV, salvar primeiro
            if tlv_field_num is not None and tlv_data:
                tlv_str = ",".join(f"TLV-{k}:{v}" for k, v in tlv_data.items())
                campos[tlv_field_num] = tlv_str
                tlv_field_num = None
                tlv_data = {}
            
            num = m.group(1).lstrip("0") or "0"
            campos[num] = m.group(2)
            last_field_num = num
            last_tlv_tag = None
        elif tlv_field_num is not None:
            # Estamos dentro de TLV, procurar tags ou continuações
            if "TLV - Bit:" in line:
                # Novo TLV encontrado, salvar o anterior
                if tlv_data:
                    tlv_str = ",".join(f"TLV-{k}:{v}" for k, v in tlv_data.items())
                    campos[tlv_field_num] = tlv_str
                    tlv_data = {}
                # Iniciar novo TLV
                tlv_m = re.search(r'TLV - Bit:(\d+)', line)
                if tlv_m:
                    tlv_field_num = tlv_m.group(1).lstrip("0") or "0"
                    last_tlv_tag = None
            elif line.strip().startswith("["):
                # Continuação de valor TLV (quebrada em múltiplas linhas)
                c = continuation_re.match(line)
                if c and last_tlv_tag is not None:
                    tlv_data[last_tlv_tag] = tlv_data.get(last_tlv_tag, "") + c.group(1)
            else:
                # Procurar por tag TLV dentro do mesmo TLV
                tlv_tag_m = re.match(r'^\s+(\d+)\s*\(\s*\d+\s*\)\s*\[([^\]]*)\]', line)
                if tlv_tag_m:
                    tag = tlv_tag_m.group(1).lstrip("0") or "0"
                    value = tlv_tag_m.group(2)
                    tlv_data[tag] = value
                    last_tlv_tag = tag
        else:
            # Fora de TLV, procurar continuações normais
            c = continuation_re.match(line)
            if c:
                cont = c.group(1)
                if "TLV - Bit:" in cont:
                    # Início de TLV
                    tlv_m = re.search(r'TLV - Bit:(\d+)', cont)
                    if tlv_m:
                        tlv_field_num = tlv_m.group(1).lstrip("0") or "0"
                        tlv_data = {}
                        last_tlv_tag = None
                        last_field_num = None
                elif last_field_num is not None:
                    campos[last_field_num] = f"{campos.get(last_field_num, '')}{cont}"
        
        i += 1
    
    # Salvar último TLV se houver
    if tlv_field_num is not None and tlv_data:
        tlv_str = ",".join(f"TLV-{k}:{v}" for k, v in tlv_data.items())
        campos[tlv_field_num] = tlv_str
    
    return campos, i


def extract_messages_from_log(log_text: str, comunicacao_tipo: str = "ISO") -> List[Dict[str, Any]]:
    messages = []
    lines = log_text.split("\n")

    _message_order = 0  # rastreia ordem de aparição no log
    i = 0
    while i < len(lines):
        line = lines[i]

        # --- Tipo 0: mensagem recebida da Processadora (ISO . NUCLEO) ---
        if "Mensagem recebida da Processadora (PROCESSADORA -> FEPAS)" in line:
            i += 1
            campos, i = _extract_message_fields(lines, i)
            mti = _normalize_mti(campos.get("1", ""))
            if mti:
                messages.append({
                    "mti": mti,
                    "campos": campos,
                    "direcao": "PROC->FEPAS",
                    "_order": _message_order,  # rastreia ordem no log
                })
                _message_order += 1
            continue

        # --- Tipo 1: mensagem recebida do Módulo TEF (apenas ISO) ---
        if comunicacao_tipo == "ISO" and "Mensagem recebida do Modulo TEF (MODULO TEF -> FEPAS)" in line:
            i += 1
            campos, i = _extract_message_fields(lines, i)
            mti = _normalize_mti(campos.get("1", ""))
            if mti:
                messages.append({
                    "mti": mti,
                    "campos": campos,
                    "direcao": "TEF->FEPAS",
                    "_order": _message_order,  # rastreia ordem no log
                })
                _message_order += 1
            continue

        # --- Tipo 1b: mensagem enviada a Processadora (FEPAS -> PROCESSADORA) ---
        if comunicacao_tipo == "ISO" and "Mensagem  enviada a Processadora (FEPAS -> PROCESSADORA)" in line:
            i += 1
            campos, i = _extract_message_fields(lines, i)
            mti = _normalize_mti(campos.get("1", ""))
            if mti:
                messages.append({
                    "mti": mti,
                    "campos": campos,
                    "direcao": "FEPAS->PROC",
                    "_order": _message_order,  # rastreia ordem no log
                })
                _message_order += 1
            continue

        # --- Tipo 2a: resposta da processadora via WEBS-RX (ISO ou WEBSERVICE) ---
        webs_rx_m = re.search(r'WEBS-RX:\s*(\{.*)', line)
        if webs_rx_m:
            json_str = webs_rx_m.group(1).strip().rstrip(".")
            try:
                data = json.loads(json_str)
                mti = _normalize_mti(data.get("CODMSG"))
                campos = {}
                for key, val in data.items():
                    if key.startswith("BIT_"):
                        num = key[4:].lstrip("0") or "0"
                        campos[num] = str(val)
                if mti:
                    messages.append({
                        "mti": mti,
                        "campos": campos,
                        "direcao": "PROC->FEPAS" if comunicacao_tipo == "ISO" else "WEB-RX",
                        "_order": _message_order,  # rastreia ordem no log
                    })
                    _message_order += 1
            except (json.JSONDecodeError, ValueError):
                pass

            i += 1
            continue

        # --- Tipo 2b: mensagem enviada via WEBS-TX (ISO ou WEBSERVICE) ---
        webs_tx_m = re.search(r'WEBS-TX:\s*(\{.*)', line)
        if webs_tx_m:
            json_str = webs_tx_m.group(1).strip().rstrip(".")
            try:
                data = json.loads(json_str)
                mti = _normalize_mti(data.get("CODMSG"))
                campos = {}
                for key, val in data.items():
                    if key.startswith("BIT_"):
                        num = key[4:].lstrip("0") or "0"
                        campos[num] = str(val)
                if mti:
                    # Para ISO: WEBS-TX é TEF->PROC (transação 0200/0400)
                    # Para WEBSERVICE: WEBS-TX é envio do cliente
                    direcao = "TEF->FEPAS" if comunicacao_tipo == "ISO" else "WEB-TX"
                    messages.append({
                        "mti": mti,
                        "campos": campos,
                        "direcao": direcao,
                        "_order": _message_order,  # rastreia ordem no log
                    })
                    _message_order += 1
            except (json.JSONDecodeError, ValueError):
                pass

        i += 1

    return messages


def parse_iso_message(raw: str) -> Dict[str, Any]:
    """
    Parse básico de mensagem ISO 8583.
    Retorna: {mti, bitmap_hex, campos: {num: valor}, erros}
    """
    result = {"mti": None, "bitmap": None, "campos": {}, "erros": []}
    
    # Remove espaços e quebras
    msg = raw.replace(" ", "").replace("\n", "").upper()
    
    if len(msg) < 8:
        result["erros"].append("Mensagem muito curta")
        return result
    
    # MTI (primeiros 4 caracteres)
    result["mti"] = msg[0:4]
    
    # Bitmap primário (próximos 16 hex = 8 bytes = 64 bits)
    if len(msg) < 20:
        result["erros"].append("Bitmap primário incompleto")
        return result
    
    bitmap_hex = msg[4:20]
    result["bitmap"] = bitmap_hex
    
    # Validação básica do bitmap
    try:
        int(bitmap_hex, 16)
    except ValueError:
        result["erros"].append(f"Bitmap inválido: {bitmap_hex}")
        return result
    
    # Extração simplificada de campos (parse de comprimento variável)
    # Para agora, apenas registramos a presença
    msg_body = msg[20:]
    
    # Padrão: campos de DE3 a DE128, variáveis em comprimento
    # Aqui fazemos apenas extração simples baseada em padrões do log
    
    return result


def validate_message_against_roteiro(msg: Dict[str, Any], roteiro: dict, teste_id: str, product_type: str = "credito") -> Dict[str, Any]:
    """
    Valida uma mensagem contra o roteiro configurado.
    Suporta múltiplas variantes de MTI por product_type (ex: 0200 vs 0200_pagamento_fatura).
    """
    validation = {
        "mti": msg["mti"],
        "teste_id": teste_id,
        "aprovado": True,
        "avisos": [],
        "erros": []
    }
    
    # Erros no parse
    if msg.get("erros"):
        validation["erros"].extend(msg["erros"])
        validation["aprovado"] = False
        return validation
    
    mti = msg["mti"]
    allowed_mtis = set(roteiro.get("allowed_mtis", []))
    
    # Validar MTI contra allowed_mtis do roteiro
    if allowed_mtis and mti not in allowed_mtis:
        validation["erros"].append(f"MTI '{mti}' não permitido pelo roteiro")
        validation["aprovado"] = False
    else:
        validation["avisos"].append(f"MTI '{mti}' permitido")
    
    # Validar bits obrigatórios
    required_bits = set(roteiro.get("required_bits", []))
    bitmap_int = int(msg.get("bitmap", "0"), 16)
    
    bits_presentes = set()
    for i in range(64):
        if bitmap_int & (1 << (63 - i)):
            bits_presentes.add(str(i + 1))
    
    faltando = required_bits - bits_presentes
    if faltando:
        validation["avisos"].append(f"Bits obrigatórios faltando: {sorted(faltando)}")
    
    # Validação específica do MTI (com suporte a variantes por product_type)
    mti_bit_rules = roteiro.get("mti_bit_rules", {})
    mti_key = get_mti_key_for_product_type(mti, product_type)
    mti_config = mti_bit_rules.get(mti_key)
    
    if mti_config:
        mti_required = set(mti_config.get("required_bits", []))
        mti_faltando = mti_required - bits_presentes
        if mti_faltando:
            validation["avisos"].append(f"Bits obrigatórios para MTI {mti_key}: {sorted(mti_faltando)}")
    
    return validation


def main():
    """Executa validação do log CARDSE."""
    
    # Carregar roteiro
    try:
        roteiro = load_roteiro()
    except FileNotFoundError:
        print(f"Erro: Roteiro não encontrado em {ROTEIRO_PATH}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Erro ao parsear roteiro: {e}")
        sys.exit(1)
    
    # Pedir arquivo de log
    log_path = input(f"Informe o caminho do arquivo de log (ou apenas o nome, pasta padrão: {DEFAULT_LOGS_DIR}): ").strip()
    
    if not log_path:
        log_path = os.path.join(DEFAULT_LOGS_DIR, "aud_20260310_autorizador.txt")
    elif not os.path.isabs(log_path):
        candidate = os.path.join(DEFAULT_LOGS_DIR, log_path)
        if os.path.exists(candidate):
            log_path = candidate
    
    if not os.path.exists(log_path):
        print(f"Erro: Arquivo não encontrado: {log_path}")
        sys.exit(1)
    
    # Ler log
    print(f"\nLendo log de {log_path}...")
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        log_text = f.read()
    
    # Extrair mensagens
    messages = extract_messages_from_log(log_text)
    print(f"Extraídas {len(messages)} mensagens da processadora.\n")
    
    if not messages:
        print("Nenhuma mensagem encontrada no log!")
        return
    
    # Agrupar por MTI
    by_mti = {}
    for msg in messages:
        mti = msg["mti"]
        if mti not in by_mti:
            by_mti[mti] = []
        by_mti[mti].append(msg)
    
    print("=" * 80)
    print("RESUMO DE MENSAGENS RECEBIDAS")
    print("=" * 80)
    
    for mti in sorted(by_mti.keys()):
        count = len(by_mti[mti])
        print(f"MTI {mti}: {count} mensagem(ns)")
    
    print("\n" + "=" * 80)
    print("VALIDAÇÃO CONTRA ROTEIRO")
    print("=" * 80)
    
    # Validar cada mensagem
    homolog_tests = roteiro.get("homolog_tests", {})
    
    validacoes = []
    for msg in messages:
        # Parsear mensagem
        parsed = parse_iso_message(msg["raw"])
        parsed["mti"] = msg["mti"]
        
        # Encontrar teste correspondente
        teste_encontrado = None
        for tid, teste_cfg in homolog_tests.items():
            cadeia_req = teste_cfg.get("rule", {}).get("required_chain", [])
            mtis_esperados = [step.get("mti") for step in cadeia_req if step]
            if msg["mti"] in mtis_esperados:
                teste_encontrado = tid
                break
        
        if not teste_encontrado:
            teste_encontrado = "00"
        
        # Validar
        val_result = validate_message_against_roteiro(parsed, roteiro, teste_encontrado)
        validacoes.append(val_result)
        
        status = "[OK]" if val_result["aprovado"] else "[FAIL]"
        print(f"\n{status} MTI {val_result['mti']} | Teste {val_result['teste_id']}")
        if val_result["avisos"]:
            for aviso in val_result["avisos"]:
                print(f"  (W) {aviso}")
        if val_result["erros"]:
            for erro in val_result["erros"]:
                print(f"  (E) {erro}")
    
    # Resumo final
    print("\n" + "=" * 80)
    print("RESUMO FINAL")
    print("=" * 80)
    
    total = len(validacoes)
    aprovadas = sum(1 for v in validacoes if v["aprovado"])
    reprovadas = total - aprovadas
    
    print(f"Total de mensagens validadas: {total}")
    print(f"Aprovadas: {aprovadas} ({100*aprovadas//total if total else 0}%)")
    print(f"Reprovadas: {reprovadas} ({100*reprovadas//total if total else 0}%)")
    print(f"Roteiro utilizado: {roteiro.get('teste', 'Sem nome')}")
    print(f"Versão: {roteiro.get('versao', 'Desconhecida')}")
    

def get_mti_key_for_product_type(mti: str, product_type: str) -> str:
    """
    Mapeia MTI e product_type para a chave correta no roteiro.
    
    Exemplo:
    - mti="0200", product_type="credito" → "0200_credito"
    - mti="0200", product_type="debito" → "0200_debito"
    - mti="0200", product_type="debito/voucher" → "0200_debito" (usa regras de débito)
    - mti="0200", product_type="pagamento_fatura" → "0200_pagamento_fatura"
    - mti="0210", product_type="credito" → "0210_credito"
    - mti="0210", product_type="pagamento_fatura" → "0210_pagamento_fatura"
    - mti="0202", product_type="debito" → "0202_debito"
    - mti="0202", product_type="pagamento_fatura" → "0202_pagamento_fatura"
    - mti="0212", product_type="credito" → "0212_credito"
    - mti="0212", product_type="pagamento_fatura" → "0212_pagamento_fatura"
    """
    # Converter debito/voucher para debito para mapeamento de bits
    if product_type == "debito/voucher":
        product_type = "debito"
    
    if mti in {"0200", "0210", "0202", "0212"}:
        if product_type == "credito":
            return f"{mti}_credito"
        if product_type == "debito":
            return f"{mti}_debito"
        if product_type == "pagamento_fatura":
            return f"{mti}_pagamento_fatura"
    return mti


def validar_mensagens_processadora(
    log_text: str,
    teste_id: str = "",
    de11: str = "",
    de42: str = "",
    cliente: str = "LOCAL",
    product_type: str = "credito",
    comunicacao_tipo: str = "ISO",
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Função de compatibilidade para usar o validador CARDSE via API.
    Valida mensagens do log no formato FEPAS (.fps.txt).

    Args:
        log_text: Conteúdo do arquivo de log
        teste_id: ID do teste sendo validado
        de11: Bit 11 (STAN) para filtrar a transação
        de42: Bit 42 (Identificação do Estabelecimento) para filtrar a transação
        cliente: ID do cliente (CNPJ)
        product_type: Tipo de produto
        comunicacao_tipo: "ISO" (padrão) ou "WEBSERVICE"
        debug: Ativa logs de debug
    """
    roteiro = load_roteiro()

    # Extrair TODAS as mensagens do log (todas as direções)
    all_messages = extract_messages_from_log(log_text, comunicacao_tipo=comunicacao_tipo)

    if not all_messages:
        return {
            "status": "FALHA",
            "resumo": "Nenhuma mensagem encontrada no log. Verifique se o arquivo é do formato FEPAS (.fps.txt).",
            "teste_id": str(teste_id or "").zfill(2),
            "total_pernas": 0,
            "total_mensagens": 0,
            "blocos_processados": 0,
            "blocos_reprovados": [],
            "campos_faltantes": {},
            "erros": ["Nenhuma mensagem encontrada"],
        }

    # --- Filtrar por DE11 e DE42 ---
    de11_f = str(de11 or "").strip()
    de42_f = str(de42 or "").strip()

    def _extract_bit90_original_stan(msg: Dict[str, Any]) -> str:
        """
        Extrai o STAN original do Bit 90 de uma mensagem de desfazimento.
        Bit 90 estrutura: [0:2]=tipo [2:4]=? [4:10]=STAN_ORIGINAL [10:...]
        Exemplo: "020004001103041425150000..." → STAN original = "040011"
        """
        bit90 = str(msg.get("campos", {}).get("90") or "").strip()
        if len(bit90) >= 10:
            return bit90[4:10]
        return ""

    def _matches_strict(msg: Dict[str, Any]) -> bool:
        campos = msg.get("campos") or {}
        if de11_f and campos.get("11", "") != de11_f:
            return False
        if de42_f:
            c42 = str(campos.get("42", "") or "").strip()
            if _normalize_numeric_text(c42) != _normalize_numeric_text(de42_f):
                return False
        return True

    def _matches_relaxed_same_trn(msg: Dict[str, Any]) -> bool:
        """
        Relaxa DE42 para incluir pernas da mesma TRN quando a mensagem não carregar DE42,
        mantendo DE11 como chave principal de correlação.
        
        Para MTIs 0420/0402/0430 (desfazimentos), também verifica Bit 90 para encontrar
        transações de reversa que referenciam a TRN original via Bit 90.
        """
        campos = msg.get("campos") or {}
        mti = msg.get("mti", "")
        
        # Para MTIs de desfazimento/reversa, verificar Bit 90
        if mti in ("0420", "0402", "0430"):
            if de11_f:
                bit90_stan = _extract_bit90_original_stan(msg)
                if bit90_stan and bit90_stan == de11_f:
                    # Mensagem de reversa/desfazimento da transação original
                    if de42_f:
                        c42 = str(campos.get("42", "") or "").strip()
                        if c42 and _normalize_numeric_text(c42) != _normalize_numeric_text(de42_f):
                            return False
                    return True
                # Tentar também Bit 11 direto (compatibilidade)
                if campos.get("11", "") == de11_f:
                    if de42_f:
                        c42 = str(campos.get("42", "") or "").strip()
                        if c42 and _normalize_numeric_text(c42) != _normalize_numeric_text(de42_f):
                            return False
                    return True
                return False
        
        # Para outras MTIs, usar lógica original (Bit 11 direto)
        if de11_f and campos.get("11", "") != de11_f:
            return False

        if de42_f:
            c42 = str(campos.get("42", "") or "").strip()
            if c42:
                if _normalize_numeric_text(c42) != _normalize_numeric_text(de42_f):
                    return False
            # se não houver DE42 nesta perna, aceita para não quebrar cadeia da TRN
        return True

    strict_messages = [m for m in all_messages if _matches_strict(m)]

    if de11_f and de42_f:
        # Se existe âncora estrita DE11+DE42, amplia para todas as pernas da mesma TRN (DE11)
        # permitindo mensagens sem DE42, para não marcar 0210 como ausente indevidamente.
        if strict_messages:
            messages = [m for m in all_messages if _matches_relaxed_same_trn(m)]
        else:
            messages = []
    else:
        messages = strict_messages if de42_f else [m for m in all_messages if _matches_relaxed_same_trn(m)]

    if not messages:
        filtro_desc = []
        if de11_f:
            filtro_desc.append(f"DE11={de11_f}")
        if de42_f:
            filtro_desc.append(f"DE42={de42_f}")
        filtro_str = " e ".join(filtro_desc) if filtro_desc else "filtros informados"

        # Mostrar DE11 disponíveis no log para ajudar o usuário
        de11_disponiveis = sorted({m["campos"].get("11", "") for m in all_messages if m["campos"].get("11", "")})
        dica = f" Bit 11 (STAN) encontrados no log: {', '.join(de11_disponiveis)}." if de11_disponiveis else ""

        return {
            "status": "FALHA",
            "resumo": f"Nenhuma mensagem encontrada com {filtro_str}. Verifique os valores informados.{dica}",
            "teste_id": str(teste_id or "").zfill(2),
            "total_pernas": 0,
            "total_mensagens": len(all_messages),
            "blocos_processados": 0,
            "blocos_reprovados": [],
            "campos_faltantes": {},
            "erros": [f"Transação com {filtro_str} não encontrada no log ({len(all_messages)} mensagens no total).{dica}"],
        }

    # --- Identificar teste e cadeia esperada ---
    homolog_tests = roteiro.get("homolog_tests", {})
    teste_id_norm = str(teste_id or "").strip().zfill(2)

    if teste_id_norm not in homolog_tests:
        return {
            "status": "FALHA",
            "resumo": f"Teste '{teste_id_norm}' não encontrado no roteiro.",
            "teste_id": teste_id_norm,
            "total_pernas": 0,
            "total_mensagens": len(all_messages),
            "blocos_processados": 0,
            "blocos_reprovados": [],
            "campos_faltantes": {},
            "erros": [f"Teste {teste_id_norm} inválido"],
        }

    teste_cfg = homolog_tests[teste_id_norm]
    product_type_eff = teste_cfg.get("product_type", product_type)
    cadeia_req = teste_cfg.get("rule", {}).get("required_chain", [])
    mtis_esperados = [str(step.get("mti") or "") for step in cadeia_req if step]

    # Separar mensagens por direção
    messages_proc = [m for m in messages if m.get("direcao") in ("PROC->FEPAS", "WEB-RX")]
    messages_tef = [m for m in messages if m.get("direcao") == "TEF->FEPAS"]
    messages_fepas_to_proc = [m for m in messages if m.get("direcao") == "FEPAS->PROC"]
    
    # MTIs encontrados (tanto ENVIADOS quanto RECEBIDOS)
    # Para validar cadeia, considerar TODAS as direções relevantes
    mtis_encontrados = [m["mti"] for m in messages if m.get("direcao") in ("PROC->FEPAS", "WEB-RX", "TEF->FEPAS", "FEPAS->PROC")]
    mtis_set = set(mtis_encontrados)

    erros: List[str] = []
    blocos_reprovados = []

    # Verificar se cada MTI da cadeia obrigatória está presente (apenas nas mensagens PROC->FEPAS)
    for mti_esp in mtis_esperados:
        if mti_esp and mti_esp not in mtis_set:
            erros.append(f"MTI {mti_esp} esperado na cadeia do teste {teste_id_norm} não encontrado.")
            blocos_reprovados.append({"mti": mti_esp, "erros": [f"MTI {mti_esp} ausente"]})

    # Validar cada mensagem encontrada contra regras de campo do roteiro
    validacoes = []
    mti_bit_rules = roteiro.get("mti_bit_rules", {})
    
    # Validar mensagens da Processadora (PROC->FEPAS): verificar bits obrigatórios
    for msg in messages_proc:
        mti_key = get_mti_key_for_product_type(msg["mti"], product_type_eff)
        mti_config = mti_bit_rules.get(mti_key) or mti_bit_rules.get(msg["mti"])
        val_erros: List[str] = []
        campos_msg = msg.get("campos") or {}

        if mti_config:
            for bit_req in (mti_config.get("required_bits") or []):
                # Normaliza leading-zeros: "01"->"1", "03"->"3", "47"->"47"
                bit_key = str(bit_req).lstrip("0") or "0"
                if bit_key not in campos_msg:
                    val_erros.append(f"Bit {bit_req} obrigatório ausente na mensagem MTI {msg['mti']}")
            
            # Validar IDs TLV obrigatórios para voucher (debito/voucher)
            if "voucher" in product_type_eff and "voucher_required_ids" in mti_config:
                bit47_value = campos_msg.get("47", "")
                voucher_ids = mti_config.get("voucher_required_ids", [])
                for tlv_id in voucher_ids:
                    tlv_pattern = f"TLV-{tlv_id}:"
                    if tlv_pattern not in str(bit47_value):
                        val_erros.append(f"TLV ID {tlv_id} obrigatório ausente no Bit 47 da mensagem MTI {msg['mti']} (transação voucher)")

        aprovado = len(val_erros) == 0
        validacoes.append({
            "mti": msg["mti"],
            "direcao": msg.get("direcao", "-"),
            "aprovado": aprovado,
            "erros": val_erros,
            "campos": campos_msg,  # Incluir todos os campos para evidência
        })
        if not aprovado:
            erros.extend(val_erros)
            blocos_reprovados.append({"mti": msg["mti"], "erros": val_erros})
    
    # Validar mensagens do TEF (TEF->FEPAS): verificar Bit 22 apenas em 0200 e 0400
    for msg in messages_tef:
        val_erros: List[str] = []
        campos_msg = msg.get("campos") or {}
        mti = msg["mti"]
        
        # Bit 22 deve estar presente APENAS em 0200 e 0400 (TEF->FEPAS)
        # Não valida em 0202, 0402, etc
        if mti in ("0200", "0400"):
            if "22" not in campos_msg:
                val_erros.append(f"Bit 22 ausente na mensagem MTI {mti} (TEF->FEPAS)")
            else:
                # Validar coerência do Bit 22 com o teste (pode ser personalizado conforme teste)
                bit22 = campos_msg.get("22", "")
                
                # Validar Bit 22 conforme regras do teste (se aplicável)
                bit22_required_prefixes = teste_cfg.get("bit22_required_prefixes", [])
                if bit22_required_prefixes:
                    # Pegar primeiros 2 dígitos do Bit 22
                    bit22_prefix = str(bit22)[:2]
                    if bit22_prefix not in bit22_required_prefixes:
                        expected = "' ou '".join(bit22_required_prefixes)
                        val_erros.append(
                            f"Bit 22 inválido na mensagem MTI {mti}: '{bit22_prefix}' "
                            f"(esperado: '{expected}'). {teste_cfg.get('bit22_description', '')}"
                        )
        
        aprovado = len(val_erros) == 0
        validacoes.append({
            "mti": mti,
            "direcao": msg.get("direcao", "-"),
            "aprovado": aprovado,
            "erros": val_erros,
            "campos": campos_msg,  # Incluir todos os campos para evidência
        })
        if not aprovado:
            erros.extend(val_erros)
            blocos_reprovados.append({"mti": mti, "erros": val_erros})
    
    # Validar mensagens FEPAS->PROC (apenas coletar dados, sem validações obrigatórias)
    for msg in messages_fepas_to_proc:
        val_erros: List[str] = []
        # Mensagens FEPAS->PROC são apenas coletadas para evidência
        # Sem validações obrigatórias de bits
        
        aprovado = True  # Sempre aprovadas por padrão (apenas coleta)
        validacoes.append({
            "mti": msg["mti"],
            "direcao": msg.get("direcao", "-"),
            "aprovado": aprovado,
            "erros": val_erros,
            "campos": msg.get("campos", {}),  # Incluir todos os campos para evidência
        })

    cadeia_ok = all(mti in mtis_set for mti in mtis_esperados if mti)

    status = "APROVADO" if cadeia_ok and len(erros) == 0 else "REPROVADO"
    
    # Construir passos_objetivo a partir do campo "steps" do roteiro
    passos_objetivo = []
    if "steps" in teste_cfg:
        for idx, step in enumerate(teste_cfg["steps"], start=1):
            mti = step.get("mti", "")
            encontrado = mti in mtis_set
            status_passo = "ENCONTRADO" if encontrado else "NÃO ENCONTRADO"
            passos_objetivo.append({
                "ordem": idx,
                "label": step.get("descricao", f"Passo {idx}"),  # label usado pelo frontend
                "mti": mti,
                "descricao": step.get("descricao", f"Passo {idx}"),
                "status": status_passo,
                "aprovado": encontrado,  # True/False para renderizar cor correta
                "motivo": "",  # motivo vazio por padrão
            })
    
    # Mapear validacoes para pernas (formato esperado pelo frontend)
    # Ordenar mensagens pela ordem original do log (usando _order)
    pernas = []
    
    # Criar mapa: _order -> validacao (usa _order como chave primária para evitar conflitos)
    val_by_order = {}
    for msg in sorted([m for m in messages_proc + messages_tef + messages_fepas_to_proc], 
                      key=lambda m: m.get("_order", float('inf'))):
        mti = msg.get("mti", "")
        direcao = msg.get("direcao", "-")
        campos = msg.get("campos", {})
        
        # Procurar validação correspondente
        val_erros = []
        val_aprovado = True
        
        # Encontrar erros na lista de validacoes
        for val in validacoes:
            if val.get("mti") == mti and val.get("direcao") == direcao:
                val_erros = val.get("erros", [])
                val_aprovado = val.get("aprovado", True)
                break
        
        # Construir ISO bruto formatado (como seria exibido no log)
        iso_bruto_lines = []
        iso_bruto_lines.append(f"MTI: {mti}")
        for campo_num in sorted(campos.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            valor = campos[campo_num]
            iso_bruto_lines.append(f"DE{campo_num}: {valor}")
        iso_bruto_str = "\n".join(iso_bruto_lines)
        
        # Mapear direcao para fluxo legível (ex: "TEF->FEPAS" → "TEF > FEPAS")
        fluxo_map = {
            "TEF->FEPAS": "TERMINAL > FEPAS",
            "PROC->FEPAS": "PROCESSADORA > FEPAS",
            "WEB-TX": "TERMINAL > FEPAS",
            "WEB-RX": "PROCESSADORA > FEPAS",
            "-": "DESCONHECIDO"
        }
        fluxo = fluxo_map.get(direcao, direcao.replace("->", " > ") if "->" in direcao else direcao)
        
        perna = {
            "ordem_log": len(pernas) + 1,
            "mti": mti,
            "direcao": direcao,
            "fluxo": fluxo,  # Interação legível (ex: "TERMINAL > FEPAS")
            "de03": campos.get("3", "-"),
            "de11": campos.get("11", "-"),
            "de41": campos.get("41", "-"),
            "de42": campos.get("42", "-"),
            "aprovado": val_aprovado,  # boolean para renderizar cores
            "status": "APROVADO" if val_aprovado else "REPROVADO",
            "motivo": " | ".join(val_erros) if val_erros else "-",
            "erros": val_erros,
            "avisos": [],
            "iso_formatado": iso_bruto_str,
            "raw_iso": iso_bruto_str,
            "campos_completos": campos,
        }
        pernas.append(perna)

    return {
        "status": status,
        "resumo": f"Cadeia {'completa' if cadeia_ok else 'incompleta'}: {', '.join(mtis_encontrados) or '(nenhum)'} | {len([p for p in pernas if p['aprovado']])}/{len(pernas)} mensagens válidas.",
        "teste": {
            "id": teste_id_norm,
            "nome": teste_cfg.get("nome", ""),
            "objetivo_esperado": teste_cfg.get("objetivo_esperado", ""),
        },
        "teste_id": teste_id_norm,
        "total_pernas": len(pernas),
        "total_mensagens": len(all_messages),
        "blocos_processados": len(pernas),
        "blocos_reprovados": blocos_reprovados,
        "campos_faltantes": {},
        "erros": erros,
        "validacoes": validacoes,
        "pernas": pernas,  # formato esperado pelo frontend
        "mtis_encontrados": mtis_encontrados,
        "mtis_esperados": mtis_esperados,
        "passos_objetivo": passos_objetivo,
    }


if __name__ == "__main__":
    main()
