from __future__ import annotations

import os
import re
from copy import deepcopy
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

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = Path(os.environ.get("HOMOLOG_LOGS_DIR", DEFAULT_LOGS_DIR)).resolve()
MAX_LOG_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".log"}

_CACHE_LOCK = Lock()
_TEXT_CACHE: Dict[Tuple[str, int, int], str] = {}
_VALIDATION_CACHE: Dict[Tuple[str, int, int, str, str, str, bool], Dict[str, Any]] = {}


def _cache_key_for_file(path: Path) -> Tuple[str, int, int]:
    stat = path.stat()
    return (str(path.resolve()).lower(), stat.st_mtime_ns, stat.st_size)


def _safe_log_name(log_name: str) -> str:
    return Path(str(log_name or "").strip()).name


def _resolve_log_path(log_name: str) -> Path:
    safe_name = _safe_log_name(log_name)
    if not safe_name:
        raise ValueError("Selecione um arquivo de log.")

    path = (LOGS_DIR / safe_name).resolve()
    if path.parent != LOGS_DIR:
        raise ValueError("Nome de arquivo inválido.")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Extensão de log inválida. Use .txt ou .log.")
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {safe_name}")
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
    result["api_metadata"] = {
        "log_name": path.name,
        "log_size_bytes": file_key[2],
        "cached": False,
    }

    with _CACHE_LOCK:
        _VALIDATION_CACHE.clear()
        _VALIDATION_CACHE[cache_key] = deepcopy(result)

    return result