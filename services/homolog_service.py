from __future__ import annotations

import json
import os
import re
import shutil
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Tuple

from validador_0200 import (
    DEFAULT_LOGS_DIR,
    _get_homolog_tests,
    avaliar_teste_homologacao_web,
    load_roteiro,
    parse_iso_formatted_blocks,
)

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = Path(os.environ.get("HOMOLOG_LOGS_DIR", DEFAULT_LOGS_DIR)).resolve()
CLIENT_HOMOLOG_DIR = Path(os.environ.get("HOMOLOG_CLIENT_STORE_DIR", BASE_DIR / "HOMOLOGACAO_CLIENTES")).resolve()
MAX_LOG_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".log"}

_CACHE_LOCK = Lock()
_TEXT_CACHE: Dict[Tuple[str, int, int], str] = {}
_VALIDATION_CACHE: Dict[Tuple[str, int, int, str, str, str, bool], Dict[str, Any]] = {}


def _safe_filename_part(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    normalized = re.sub(r"_+", "_", normalized).strip("._-")
    return normalized or "arquivo"


def _normalize_client_id(value: str) -> str:
    normalized = _safe_filename_part(value)
    if normalized == "arquivo":
        raise ValueError("Informe um cliente válido.")
    return normalized.lower()


def _normalize_cnpj(value: str) -> str:
    normalized = _safe_filename_part(str(value or "").strip())
    if normalized == "arquivo":
        raise ValueError("Informe o CNPJ do cliente.")
    return normalized


def _normalize_product_id(value: str) -> str:
    """Normaliza o ID do produto para nome descritivo.
    01 -> 01_QRCARDSE
    02 -> 02_AutorizadorCARDSE
    """
    normalized = str(value or "").strip()
    # Se já é formato descritivo completo, retorna como está
    if normalized in ("01_QRCARDSE", "02_AutorizadorCARDSE"):
        return normalized
    # Se for número, converte
    normalized = normalized.zfill(2)
    if normalized == "02":
        return "02_AutorizadorCARDSE"
    return "01_QRCARDSE"  # Padrão QR


def _client_root_dir(cnpj: str, produto_id: str = None) -> Path:
    """Retorna o diretório raiz do cliente.
    Se produto_id for informado, separa por produto: CLIENTES/{produto_id}/{cnpj}
    Caso contrário (compatibilidade): CLIENTES/{cnpj}
    """
    base = CLIENT_HOMOLOG_DIR
    if produto_id:
        pid_norm = _normalize_product_id(produto_id)
        base = base / pid_norm
    return base / _normalize_cnpj(cnpj)


def _client_stats_path(cnpj: str, produto_id: str = None) -> Path:
    return _client_root_dir(cnpj, produto_id) / "stats.json"


def _catalog_tests() -> List[Dict[str, Any]]:
    return list(get_tests_payload().get("tests") or [])


def _catalog_tests_by_id() -> Dict[str, Dict[str, Any]]:
    return {str(item.get("id") or "").zfill(2): item for item in _catalog_tests()}


def _compute_progress_summary(stats: Dict[str, Any], total_catalog_tests: int) -> Dict[str, Any]:
    assigned_tests = [str(item).zfill(2) for item in (stats.get("assigned_tests") or []) if str(item).strip()]
    tests = stats.get("tests") or {}
    started = 0
    approved = 0
    tracked_items = [tests.get(test_id) or {} for test_id in assigned_tests] if assigned_tests else list(tests.values())
    for item in tracked_items:
        attempts = int(item.get("attempts_total") or 0)
        approved_once = bool(item.get("approved_once"))
        if attempts > 0:
            started += 1
        if approved_once:
            approved += 1

    planned_tests = len(assigned_tests)
    denominator = planned_tests if planned_tests > 0 else total_catalog_tests
    overall_percent = round((approved / denominator) * 100, 2) if denominator > 0 else 0.0
    return {
        "total_testes_catalogo": total_catalog_tests,
        "total_testes_planejados": planned_tests,
        "testes_iniciados": started,
        "testes_aprovados": approved,
        "percentual_aprovacao_geral": overall_percent,
    }


def _default_client_stats(cnpj: str, produto_id: str = None) -> Dict[str, Any]:
    total_catalog_tests = len(_catalog_tests())
    return {
        "cnpj": _normalize_cnpj(cnpj),
        "updated_at": "",
        "assigned_tests": [],
        "onboarding_completed": False,
        "tests": {},
        "resumo": _compute_progress_summary({"tests": {}}, total_catalog_tests),
    }


def _load_client_stats(cnpj: str, produto_id: str = None) -> Dict[str, Any]:
    stats_path = _client_stats_path(cnpj, produto_id)
    if not stats_path.is_file():
        return _default_client_stats(cnpj, produto_id)

    try:
        loaded = json.loads(stats_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _default_client_stats(cnpj, produto_id)

    total_catalog_tests = len(_catalog_tests())
    loaded.setdefault("cnpj", _normalize_cnpj(cnpj))
    loaded.setdefault("assigned_tests", [])
    loaded.setdefault("onboarding_completed", bool(loaded.get("assigned_tests")))
    loaded.setdefault("tests", {})
    loaded["resumo"] = _compute_progress_summary(loaded, total_catalog_tests)
    return loaded


def _save_client_stats(cnpj: str, stats: Dict[str, Any], produto_id: str = None) -> Dict[str, Any]:
    root_dir = _client_root_dir(cnpj, produto_id)
    root_dir.mkdir(parents=True, exist_ok=True)

    total_catalog_tests = len(_catalog_tests())
    stats = dict(stats)
    stats["cnpj"] = _normalize_cnpj(cnpj)
    stats["updated_at"] = datetime.now().isoformat(timespec="seconds")
    stats["assigned_tests"] = [str(item).zfill(2) for item in (stats.get("assigned_tests") or []) if str(item).strip()]
    stats["onboarding_completed"] = bool(stats.get("assigned_tests"))
    stats["resumo"] = _compute_progress_summary(stats, total_catalog_tests)

    stats_path = _client_stats_path(cnpj, produto_id)
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def _build_test_progress_payload(test_entry: Dict[str, Any]) -> Dict[str, Any]:
    attempts_total = int(test_entry.get("attempts_total") or 0)
    approved_attempts = int(test_entry.get("approved_attempts") or 0)
    approved_once = bool(test_entry.get("approved_once"))
    attempts_until_approval = test_entry.get("attempts_until_approval")

    success_percent = round((approved_attempts / attempts_total) * 100, 2) if attempts_total > 0 else 0.0
    until_approval_percent = 0.0
    if isinstance(attempts_until_approval, int) and attempts_until_approval > 0:
        until_approval_percent = round((1 / attempts_until_approval) * 100, 2)

    return {
        "teste_id": str(test_entry.get("teste_id") or "").zfill(2),
        "teste_nome": str(test_entry.get("teste_nome") or "").strip(),
        "attempts_total": attempts_total,
        "approved_attempts": approved_attempts,
        "approved_once": approved_once,
        "attempts_until_approval": attempts_until_approval,
        "percentual_sucesso": success_percent,
        "percentual_ate_aprovacao": until_approval_percent,
        "status": "APROVADO" if approved_once else ("EM_ANDAMENTO" if attempts_total > 0 else "NAO_INICIADO"),
        "last_result": str(test_entry.get("last_result") or ""),
        "last_attempt_at": str(test_entry.get("last_attempt_at") or ""),
    }


def _build_empty_test_progress_payload(test_id: str, test_name: str) -> Dict[str, Any]:
    return _build_test_progress_payload(
        {
            "teste_id": str(test_id).zfill(2),
            "teste_nome": str(test_name or "").strip(),
            "attempts_total": 0,
            "approved_attempts": 0,
            "approved_once": False,
            "attempts_until_approval": None,
            "last_result": "",
            "last_attempt_at": "",
        }
    )


def _build_all_tests_progress(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    catalog_by_id = _catalog_tests_by_id()
    tests = stats.get("tests") or {}
    assigned_tests = [str(item).zfill(2) for item in (stats.get("assigned_tests") or []) if str(item).strip()]
    target_ids = assigned_tests or sorted(tests)
    output: List[Dict[str, Any]] = []

    for test_id in target_ids:
      catalog_item = catalog_by_id.get(test_id) or {}
      if test_id in tests:
          output.append(_build_test_progress_payload(tests[test_id]))
      else:
          output.append(_build_empty_test_progress_payload(test_id, str(catalog_item.get("nome") or "")))

    return output


# NOTE: enroll_client_tests() removed - use multiproduct version instead


# NOTE: _update_client_stats() removed - use multiproduct version instead


# NOTE: get_client_progress_payload() removed - use multiproduct version instead


# NOTE: list_clients_payload() removed - use multiproduct version instead


# NOTE: admin_set_client_tests() removed - use multiproduct version instead


# NOTE: admin_reset_client_onboarding() removed - use multiproduct version instead


# NOTE: admin_reset_client_tests() removed - use multiproduct version instead


def _parse_test_date(value: str) -> Tuple[str, str]:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Informe a data do teste.")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return (dt.strftime("%Y-%m-%d"), dt.strftime("%Y%m%d"))
        except ValueError:
            continue

    raise ValueError("Data do teste inválida. Use YYYY-MM-DD, DD/MM/YYYY ou YYYYMMDD.")


def _select_log_by_test_date(test_date: str, produto_id: str = None) -> Path:
    _, compact_date = _parse_test_date(test_date)
    pid = _normalize_product_id(produto_id or "01")
    
    # Buscar em LOGS_DIR/{produto_id}/
    product_logs_dir = LOGS_DIR / pid
    if not product_logs_dir.is_dir():
        raise FileNotFoundError(f"Diretório de logs não encontrado para o produto {pid}: {product_logs_dir}")

    strict_candidates: List[Path] = []
    fallback_candidates: List[Path] = []
    prefix = f"aud_{compact_date}"

    for path in product_logs_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        name = path.name.lower()
        if name.startswith(prefix):
            strict_candidates.append(path)
            continue
        if compact_date in name:
            fallback_candidates.append(path)

    candidates = strict_candidates or fallback_candidates

    if not candidates:
        raise FileNotFoundError(
            f"Nenhum log encontrado para a data {compact_date} no produto {pid}. Exemplo esperado: LOGS de TESTE/{pid}/aud_{compact_date}.txt"
        )

    candidates.sort(key=lambda p: p.stat().st_mtime_ns, reverse=True)
    return candidates[0]


def _collect_denied_legs(pernas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    denied: List[Dict[str, Any]] = []

    for leg in pernas:
        status = str(leg.get("status") or "").strip().upper()
        aprovado = leg.get("aprovado")
        if not (status == "REPROVADO" or aprovado is False):
            continue

        ordem_log = str(leg.get("ordem_log") or "-")
        mti = str(leg.get("mti") or "-")
        perna_label = f"Perna {ordem_log} (MTI {mti})"

        motivos: List[str] = []
        seen = set()

        estruturados = ((leg.get("erros_estruturados") or {}).get("all") or [])
        for entry in estruturados:
            msg = str((entry or {}).get("message") or "").strip()
            if msg and msg not in seen:
                seen.add(msg)
                motivos.append(msg)

        for msg in (leg.get("erros") or []):
            text = str(msg or "").strip()
            if text and text not in seen:
                seen.add(text)
                motivos.append(text)

        motivo_resumo = str(leg.get("motivo") or "").strip()
        if motivo_resumo and motivo_resumo not in seen:
            seen.add(motivo_resumo)
            motivos.append(motivo_resumo)

        if not motivos:
            motivos.append("Sem motivo detalhado.")

        denied.append(
            {
                "perna": perna_label,
                "motivo": motivos[0],
                "motivos": motivos,
            }
        )

    return denied


def _persist_client_test_record(
    *,
    cliente_id: str,
    test_date_iso: str,
    teste_id: str,
    de11: str,
    de41: str,
    selected_log_name: str,
    result: Dict[str, Any],
) -> Dict[str, str]:
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    safe_cliente = _normalize_client_id(cliente_id)
    date_dir = _safe_filename_part(test_date_iso)
    base_path = CLIENT_HOMOLOG_DIR / safe_cliente / date_dir
    base_path.mkdir(parents=True, exist_ok=True)

    record_id = f"{timestamp}_{_safe_filename_part(teste_id)}"
    json_name = f"{record_id}.json"
    json_path = base_path / json_name

    storage_payload = {
        "record_id": record_id,
        "saved_at": now.isoformat(timespec="seconds"),
        "cliente_id": safe_cliente,
        "data_teste": test_date_iso,
        "teste_id": str(teste_id or "").strip(),
        "de11": str(de11 or "").strip(),
        "de41": str(de41 or "").strip(),
        "log_selecionado": selected_log_name,
        "resultado_final": str(result.get("status") or "").upper(),
        "resultado_completo": result,
    }
    json_path.write_text(json.dumps(storage_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    evid = result.get("evidencia") or {}
    evid_content = str(evid.get("content") or "").strip()
    if not evid_content and str(result.get("status") or "").upper() == "APROVADO":
        generated = _build_evidence_payload(result, selected_log_name)
        evid_content = str(generated.get("content") or "").strip()
    evidence_path_str = ""
    if evid_content:
        evidence_name = f"{record_id}_evidencia.txt"
        evidence_path = base_path / evidence_name
        evidence_path.write_text(evid_content, encoding="utf-8")
        evidence_path_str = str(evidence_path)

    return {
        "record_id": record_id,
        "json_path": str(json_path),
        "evidence_path": evidence_path_str,
    }


def _collect_flow_by_header_line(result: Dict[str, Any]) -> Dict[int, Dict[str, str]]:
    flow_map: Dict[int, Dict[str, str]] = {}
    
    # Usar as pernas do resultado direto (que já têm direction e header_text)
    pernas = result.get("pernas") or []
    
    for leg in pernas:
        try:
            header_line = int(leg.get("header_line") or -1)
        except (TypeError, ValueError):
            continue

        if header_line < 0 or header_line in flow_map:
            continue

        flow_map[header_line] = {
            "direction": str(leg.get("direction") or "-").strip() or "-",
            "header_text": str(leg.get("header_text") or "-").strip() or "-",
        }
    
    # Fallback para resultado_log se não encontrar (compatibilidade com versões antigas)
    if not flow_map:
        resultado_log = result.get("resultado_log") or {}
        candidate_transactions: List[Dict[str, Any]] = []
        transacao_unica = resultado_log.get("transacao_selecionada")
        if isinstance(transacao_unica, dict):
            candidate_transactions.append(transacao_unica)
        for tx in resultado_log.get("transacoes") or []:
            if isinstance(tx, dict):
                candidate_transactions.append(tx)

        for tx in candidate_transactions:
            for leg in tx.get("pernas") or []:
                try:
                    header_line = int(leg.get("header_line"))
                except (TypeError, ValueError):
                    continue

                if header_line in flow_map:
                    continue

                flow_map[header_line] = {
                    "direction": str(leg.get("direction") or "-").strip() or "-",
                    "header_text": str(leg.get("header_text") or "-").strip() or "-",
                }

    return flow_map


def _extract_bit47_tlv_lines(iso_formatado: str) -> List[str]:
    lines = [str(line) for line in str(iso_formatado or "").splitlines()]
    extracted: List[str] = []
    in_bit47 = False
    in_subtlv = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("[TLV - Bit:47]"):
            in_bit47 = True
            in_subtlv = False
            extracted.append("[TLV - Bit:47]")
            continue

        if in_bit47 and line.startswith("[TLV - Bit:") and not line.startswith("[TLV - Bit:47]"):
            break

        if not in_bit47:
            continue

        if line.startswith("ID "):
            in_subtlv = False
            extracted.append(line)
            continue

        if line.startswith("[SubTLV - ID:"):
            in_subtlv = True
            extracted.append(f"  {line}")
            continue

        if in_subtlv and line.startswith("TAG "):
            extracted.append(f"  {line}")

    return extracted


def _strip_bit47_tlv_section(iso_formatado: str) -> str:
    lines = [str(line) for line in str(iso_formatado or "").splitlines()]
    kept: List[str] = []
    in_bit47 = False

    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("[TLV - Bit:47]"):
            in_bit47 = True
            continue

        if in_bit47 and line.startswith("[TLV - Bit:") and not line.startswith("[TLV - Bit:47]"):
            in_bit47 = False

        if in_bit47:
            continue

        kept.append(raw_line)

    return "\n".join(kept).strip()


def _build_evidence_payload(result: Dict[str, Any], log_name: str) -> Dict[str, str]:
    teste = result.get("teste") or {}
    _resumo_raw = result.get("resumo")
    resumo = _resumo_raw if isinstance(_resumo_raw, dict) else {}
    passos = result.get("passos_objetivo") or []
    pernas = result.get("pernas") or []
    motivos = result.get("motivos_status_geral") or []
    flow_by_header_line = _collect_flow_by_header_line(result)

    # Se não tem resumo, calcular a partir das pernas
    if not resumo and pernas:
        pernas_aprovadas = sum(1 for p in pernas if p.get("aprovado") is True)
        pernas_reprovadas = sum(1 for p in pernas if p.get("aprovado") is False)
        pernas_nao_aplicam = sum(1 for p in pernas if p.get("aprovado") is None)
        
        resumo = {
            "total_pernas": len(pernas),
            "pernas_aprovadas": pernas_aprovadas,
            "pernas_negadas": pernas_reprovadas,
            "pernas_nao_aplicam": pernas_nao_aplicam,
        }

    test_id = str(teste.get("id") or "00").zfill(2)
    test_name = str(teste.get("nome") or "").strip()
    status = str(result.get("status") or "-")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: List[str] = []
    lines.append("EVIDENCIA DE HOMOLOGACAO ISO 8583")
    lines.append("=" * 80)
    lines.append(f"Gerado em: {timestamp}")
    lines.append(f"Arquivo de log: {log_name}")
    lines.append(f"Teste: {test_id} - {test_name}")
    lines.append(f"Status geral: {status}")
    lines.append(f"Objetivo esperado: {teste.get('objetivo_esperado') or '-'}")
    lines.append("")
    lines.append("RESUMO")
    lines.append("-" * 80)
    lines.append(f"Total de pernas: {resumo.get('total_pernas', 0)}")
    lines.append(f"Pernas aprovadas: {resumo.get('pernas_aprovadas', 0)}")
    lines.append(f"Pernas reprovadas: {resumo.get('pernas_negadas', 0)}")
    lines.append(f"Pernas nao aplicam: {resumo.get('pernas_nao_aplicam', 0)}")

    if motivos:
        lines.append("")
        lines.append("MOTIVOS STATUS GERAL")
        lines.append("-" * 80)
        for idx, motivo in enumerate(motivos, start=1):
            lines.append(f"{idx}. {motivo}")

    if passos:
        lines.append("")
        lines.append("PASSOS DO OBJETIVO")
        lines.append("-" * 80)
        for passo in passos:
            lines.append(
                f"{passo.get('ordem', '-')} | {passo.get('label', '-')} | {passo.get('status', '-')} | {passo.get('motivo', '-') }"
            )

    lines.append("")
    lines.append("TROCA DE MENSAGENS ISO")
    lines.append("-" * 80)
    for idx, leg in enumerate(pernas, start=1):
        try:
            header_line_key = int(leg.get("header_line"))
        except (TypeError, ValueError):
            header_line_key = None
        flow_info = flow_by_header_line.get(header_line_key or -1, {})

        lines.append(f"PERNA {idx}")
        lines.append(f"Ordem no log: {leg.get('ordem_log', '-')}")
        lines.append(f"Fluxo: {flow_info.get('direction', '-')}")
        lines.append(f"Cabecalho de direcao: {flow_info.get('header_text', '-')}")
        lines.append(f"MTI: {leg.get('mti', '-')}")
        lines.append(f"DE03: {leg.get('de03', '-')}")
        lines.append(f"DE11: {leg.get('de11', '-')}")
        lines.append(f"DE41: {leg.get('de41', '-')}")
        lines.append(f"Status: {leg.get('status', '-')}")
        lines.append(f"Motivo: {leg.get('motivo', '-')}")

        raw_iso = str(leg.get("raw_iso") or "").strip()
        formatted_iso = str(leg.get("iso_formatado") or "").strip()
        formatted_iso_without_bit47 = _strip_bit47_tlv_section(formatted_iso)

        lines.append("ISO BRUTO:")
        lines.append(raw_iso or "(sem ISO bruto)")
        lines.append("ISO FORMATADO:")
        lines.append(formatted_iso_without_bit47 or formatted_iso or "(sem ISO formatado)")

        tlv47_lines = _extract_bit47_tlv_lines(formatted_iso)
        lines.append("TLV DO BIT 47 (IDS/TAGS):")
        if tlv47_lines:
            lines.extend(tlv47_lines)
        else:
            lines.append("(Bit 47 nao encontrado ou sem IDs/TAGS detalhados nesta mensagem)")
        lines.append("-" * 80)

    log_stem = Path(log_name).stem
    file_name = f"evidencia_teste_{test_id}_{_safe_filename_part(log_stem)}.txt"
    return {
        "file_name": file_name,
        "content": "\n".join(lines),
    }


def _cache_key_for_file(path: Path) -> Tuple[str, int, int]:
    stat = path.stat()
    return (str(path.resolve()).lower(), stat.st_mtime_ns, stat.st_size)


def _safe_log_name(log_name: str) -> str:
    return Path(str(log_name or "").strip()).name


def _resolve_log_path(log_name: str, produto_id: str = None) -> Path:
    safe_name = _safe_log_name(log_name)
    if not safe_name:
        raise ValueError("Selecione um arquivo de log.")

    pid = _normalize_product_id(produto_id or "01")
    product_logs_dir = LOGS_DIR / pid
    product_logs_dir.mkdir(parents=True, exist_ok=True)
    
    path = (product_logs_dir / safe_name).resolve()
    if path.parent != product_logs_dir:
        raise ValueError("Nome de arquivo inválido.")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Extensão de log inválida. Use .txt ou .log.")
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {safe_name} em LOGS de TESTE/{pid}/")
    return path


def _read_log_text(path: Path) -> str:
    stat = path.stat()
    if stat.st_size == 0:
        raise ValueError("O arquivo de log está vazio.")
    if stat.st_size > MAX_LOG_SIZE_BYTES:
        raise ValueError(
            f"O arquivo excede o limite de {MAX_LOG_SIZE_BYTES // (1024 * 1024)} MB suportado pela API."
        )

    key = _cache_key_for_file(path)
    with _CACHE_LOCK:
        cached = _TEXT_CACHE.get(key)
        if cached is not None:
            return cached

    text = path.read_text(encoding="utf-8", errors="ignore")

    with _CACHE_LOCK:
        _TEXT_CACHE.clear()
        _TEXT_CACHE[key] = text

    return text


def _extract_field_from_message(message: str) -> str | None:
    match = re.search(r"Bit\s+(\d{1,3})", message)
    if match:
        return match.group(1).zfill(2)
    match = re.search(r"ID\s?(\d{2,3})", message)
    if match:
        return match.group(1)
    match = re.search(r"TAG\s?(\d{2,3})", message)
    if match:
        return match.group(1)
    return None


def _normalize_error_message(message: str, default_origin: str, severity: str = "error") -> Dict[str, Any]:
    msg = str(message or "").strip()
    code = "GENERAL_VALIDATION_ERROR"
    source = default_origin
    domain = "general"
    field = _extract_field_from_message(msg)

    if msg.startswith("Bits obrigatórios ausentes:"):
        code = "REQUIRED_BITS_MISSING"
        source = "scenario"
        domain = "scenario"
        field = None
    elif msg.startswith("Bit 47: sub-IDs obrigatórios ausentes:"):
        code = "BIT47_REQUIRED_IDS_MISSING"
        source = "scenario"
        domain = "bit47"
        field = "47"
    elif msg.startswith("Bit 47: o primeiro ID deve ser"):
        code = "BIT47_FIRST_ID_INVALID"
        source = "bit47"
        domain = "bit47"
        field = "47"
    elif msg.startswith("Bit 47/ID") and "esperado numérico" in msg:
        code = "BIT47_ID_NUMERIC_EXPECTED"
        source = "bit47"
        domain = "bit47"
    elif msg.startswith("Bit 47/ID") and "!=" in msg:
        code = "BIT47_ID_LENGTH_EXACT_MISMATCH"
        source = "bit47"
        domain = "bit47"
    elif msg.startswith("Bit 47/ID") and " < " in f" {msg} ":
        code = "BIT47_ID_LENGTH_MIN_MISMATCH"
        source = "bit47"
        domain = "bit47"
    elif msg.startswith("Bit 47/ID") and " > " in f" {msg} ":
        code = "BIT47_ID_LENGTH_MAX_MISMATCH"
        source = "bit47"
        domain = "bit47"
    elif msg.startswith("DE47/ID238:") and "erro de parsing" in msg:
        code = "ID238_PARSE_ERROR"
        source = "id238"
        domain = "id238"
        field = "238"
    elif msg.startswith("DE47/ID238:") and "sub-TAG obrigatória ausente" in msg:
        code = "ID238_REQUIRED_TAG_MISSING"
        source = "scenario"
        domain = "id238"
        field = "238"
    elif msg.startswith("DE47/ID238") and "esperado numérico" in msg:
        code = "ID238_NUMERIC_EXPECTED"
        source = "id238"
        domain = "id238"
        field = "238"
    elif msg.startswith("DE47/ID238") and "!=" in msg:
        code = "ID238_LENGTH_EXACT_MISMATCH"
        source = "id238"
        domain = "id238"
        field = "238"
    elif msg.startswith("DE47/ID238") and "fora de" in msg:
        code = "ID238_LENGTH_RANGE_MISMATCH"
        source = "id238"
        domain = "id238"
        field = "238"
    elif msg.startswith("Scenario "):
        code = "SCENARIO_REQUIREMENT_MISSING"
        source = "scenario"
        domain = "scenario"
    elif msg.startswith("Bit ") and "esperado numérico" in msg:
        code = "BIT_NUMERIC_EXPECTED"
        domain = "field"
    elif msg.startswith("Bit ") and "!=" in msg:
        code = "BIT_LENGTH_EXACT_MISMATCH"
        domain = "field"
    elif msg.startswith("Bit ") and " < " in f" {msg} ":
        code = "BIT_LENGTH_MIN_MISMATCH"
        domain = "field"
    elif msg.startswith("Bit ") and " > " in f" {msg} ":
        code = "BIT_LENGTH_MAX_MISMATCH"
        domain = "field"
    elif msg.startswith("Cadeia esperada não encontrada") or msg.startswith("Fluxo obrigatório"):
        code = "FLOW_CHAIN_MISSING"
        source = "flow"
        domain = "flow"
    elif msg.startswith("Comparação '"):
        code = "COMPARISON_FAILED"
        source = "comparison"
        domain = "comparison"
    elif msg.startswith("Transação com DE11/DE41 informados"):
        code = "TRANSACTION_NOT_FOUND"
        source = "matching"
        domain = "matching"
        field = None
    elif msg.startswith("Nenhuma transação encontrada"):
        code = "NO_TRANSACTIONS_FOUND"
        source = "matching"
        domain = "matching"
        field = None
    elif msg.startswith("Bitmap secundário ausente/truncado"):
        code = "SECONDARY_BITMAP_UNAVAILABLE"
        source = "raw"
        domain = "bitmap"
        severity = "warning"
        field = None

    return {
        "code": code,
        "message": msg,
        "field": field,
        "source": source,
        "domain": domain,
        "severity": severity,
    }


def _structured_warning_list(messages: List[str]) -> List[Dict[str, Any]]:
    return [_normalize_error_message(msg, default_origin="warning", severity="warning") for msg in messages]


def _group_structured_entries(entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(entry["source"], []).append(entry)
    return grouped


def _decorate_leg_errors(leg: Dict[str, Any]) -> Dict[str, Any]:
    raw_entries = [_normalize_error_message(msg, default_origin="raw") for msg in leg.get("erros_raw") or []]
    formatted_entries = [
        _normalize_error_message(msg, default_origin="formatted") for msg in leg.get("erros_formatados") or []
    ]
    warning_entries = _structured_warning_list(list(leg.get("avisos") or []))

    all_entries: List[Dict[str, Any]] = []
    seen = set()
    for entry in raw_entries + formatted_entries:
        sig = (entry["code"], entry["message"], entry["source"])
        if sig in seen:
            continue
        seen.add(sig)
        all_entries.append(entry)

    leg["erros_estruturados"] = {
        "all": all_entries,
        "by_origin": {
            "raw": raw_entries,
            "formatted": formatted_entries,
        },
        "by_source": _group_structured_entries(all_entries),
        "warnings": warning_entries,
    }
    return leg


def _decorate_validation_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    pernas = [_decorate_leg_errors(dict(leg)) for leg in result.get("pernas") or []]

    overall_errors = [_normalize_error_message(msg, default_origin="general") for msg in result.get("motivos_status_geral") or []]
    overall_warnings = _structured_warning_list(list((result.get("resultado_log") or {}).get("avisos") or []))

    result = dict(result)
    result["pernas"] = pernas
    result["motivos_status_geral_estruturados"] = overall_errors
    result["diagnostico"] = {
        "errors_by_source": _group_structured_entries(overall_errors),
        "warnings": overall_warnings,
    }
    return result


def get_tests_payload() -> Dict[str, Any]:
    roteiro = load_roteiro()
    tests = _get_homolog_tests(roteiro)
    out = []
    for tid in sorted(tests.keys()):
        t = tests[tid]
        out.append(
            {
                "id": str(t.get("id") or tid).zfill(2),
                "nome": t.get("nome"),
                "descricao": t.get("descricao"),
                "objetivo_esperado": t.get("objetivo_esperado"),
            }
        )
    return {"tests": out}


def list_logs_payload() -> Dict[str, Any]:
    if not LOGS_DIR.is_dir():
        return {"logs": [], "directory": str(LOGS_DIR), "exists": False}

    logs = []
    for path in sorted(LOGS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        stat = path.stat()
        logs.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime_ns,
            }
        )
    return {"logs": logs, "directory": str(LOGS_DIR), "exists": True}


def get_api_config_payload() -> Dict[str, Any]:
    return {
        "base_dir": str(BASE_DIR),
        "logs_dir": str(LOGS_DIR),
        "logs_dir_exists": LOGS_DIR.is_dir(),
        "max_log_size_bytes": MAX_LOG_SIZE_BYTES,
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
    }


def get_health_payload() -> Dict[str, Any]:
    log_count = 0
    if LOGS_DIR.is_dir():
        log_count = sum(1 for p in LOGS_DIR.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS)

    with _CACHE_LOCK:
        text_cache_size = len(_TEXT_CACHE)
        validation_cache_size = len(_VALIDATION_CACHE)

    return {
        "status": "ok",
        "logs_dir": str(LOGS_DIR),
        "logs_dir_exists": LOGS_DIR.is_dir(),
        "available_logs": log_count,
        "cache": {
            "text_entries": text_cache_size,
            "validation_entries": validation_cache_size,
        },
    }


def get_log_summary_payload(log_name: str) -> Dict[str, Any]:
    path = _resolve_log_path(log_name)
    text = _read_log_text(path)
    blocks = parse_iso_formatted_blocks(text)
    mtis: Dict[str, int] = {}
    directions: Dict[str, int] = {}

    for block in blocks:
        mti = str((block.get("fields") or {}).get("01") or "")
        if mti:
            mtis[mti] = mtis.get(mti, 0) + 1
        direction = str(block.get("direction") or "unknown")
        directions[direction] = directions.get(direction, 0) + 1

    return {
        "log": path.name,
        "size_bytes": path.stat().st_size,
        "total_lines": len(text.splitlines()),
        "iso_blocks": len(blocks),
        "mtis": mtis,
        "directions": directions,
        "preview": text[:1000],
    }


def validate_log_payload(
    *,
    teste_id: str,
    log_name: str,
    de11: str = "",
    de41: str = "",
    cliente: str = "LOCAL",
    debug: bool = False,
) -> Dict[str, Any]:
    teste_id = str(teste_id or "").strip()
    if not teste_id:
        raise ValueError("Selecione um teste de homologação.")

    path = _resolve_log_path(log_name)
    text = _read_log_text(path)
    file_key = _cache_key_for_file(path)
    cache_key = (file_key[0], file_key[1], file_key[2], teste_id, str(de11 or ""), str(de41 or ""), bool(debug))

    with _CACHE_LOCK:
        cached = _VALIDATION_CACHE.get(cache_key)
        if cached is not None:
            cached_result = deepcopy(cached)
            cached_result.setdefault("api_metadata", {})["cached"] = True
            return cached_result

    result = avaliar_teste_homologacao_web(
        text,
        teste_id=teste_id,
        de11=str(de11 or "").strip(),
        de41=str(de41 or "").strip(),
        cliente=cliente,
        debug=debug,
    )
    result = _decorate_validation_payload(result)
    if str(result.get("status") or "") == "APROVADO":
        result["evidencia"] = _build_evidence_payload(result, path.name)
    else:
        result["evidencia"] = None

    result["api_metadata"] = {
        "log_name": path.name,
        "log_size_bytes": file_key[2],
        "cached": False,
    }

    with _CACHE_LOCK:
        _VALIDATION_CACHE.clear()
        _VALIDATION_CACHE[cache_key] = deepcopy(result)

    return result


# NOTE: validate_client_payload() removed - use multiproduct version instead