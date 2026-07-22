# services/homolog_service_multiproduct.py
"""
Extensão do serviço de homologação para suportar múltiplos produtos.
Permite seleção entre QR Pago e Autorizador CARDSE.
"""

import importlib.util
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

from products_config import get_produto, listar_produtos, get_roteiro_path, get_validador_info
from validador_0200 import load_roteiro
from services import db_store

# Importar o serviço base - importar diretamente de services.homolog_service
from services.homolog_service import (
    BASE_DIR,
    LOGS_DIR,
    CLIENT_HOMOLOG_DIR,
    MAX_LOG_SIZE_BYTES,
    ALLOWED_EXTENSIONS,
    _read_log_text,
    _resolve_log_path,
    _cache_key_for_file,
    _decorate_validation_payload,
    _build_evidence_payload,
    _CACHE_LOCK,
    _VALIDATION_CACHE,
    _normalize_cnpj,
    _normalize_product_id,
    _load_client_stats,
    _save_client_stats,
    _catalog_tests_by_id,
    _build_test_progress_payload,
    _build_all_tests_progress,
    parse_iso_formatted_blocks,
    _get_homolog_tests,
    _parse_test_date,
)


def fetch_logs_for_product_by_date(*, produto_id: str, data_teste: str, force: bool = False) -> Dict[str, Any]:
    """
    Dispara ingestão de logs por data para o produto selecionado.

    Hoje suportado para QR (produto 01_QRCARDSE), executando o script
    scripts/tools/coletor_audit_qr_http.py com --date YYYYMMDD.
    Script funciona em qualquer ambiente (Windows, Linux, Render) sem dependências externas.
    """
    pid = _normalize_product_id(produto_id)
    _, compact_date = _parse_test_date(data_teste)

    if pid != "01_QRCARDSE":
        return {
            "ok": True,
            "produto_id": pid,
            "data": compact_date,
            "executed": False,
            "summary": "Ingestão automática por data disponível apenas para o produto QR (01_QRCARDSE).",
        }

    # Script HTTP - compatível com Render
    script_path = BASE_DIR / "scripts" / "tools" / "coletor_audit_qr_http.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Script de coleta QR não encontrado: {script_path}")

    expected_name = f"aud_{compact_date}.txt"
    expected_path = LOGS_DIR / "01_QRCARDSE" / expected_name

    python_exe = sys.executable or "python"
    cmd: List[str] = [
        python_exe,
        str(script_path),
        "--date",
        compact_date,
    ]
    if force:
        cmd.append("--force")

    proc = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=60 * 20,
        shell=False,
    )

    stdout = str(proc.stdout or "").strip()
    stderr = str(proc.stderr or "").strip()

    if proc.returncode != 0:
        detail = stderr or stdout or f"Processo finalizou com código {proc.returncode}."
        raise RuntimeError(f"Falha ao coletar logs QR para {compact_date}: {detail}")

    # Se o arquivo ainda não existe após a primeira tentativa, tenta novamente com --force
    if not expected_path.exists() and not force:
        cmd.append("--force")
        proc = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=60 * 20,
            shell=False,
        )
        stdout = str(proc.stdout or "").strip()
        stderr = str(proc.stderr or "").strip()
        
        if proc.returncode != 0:
            detail = stderr or stdout or f"Processo finalizou com código {proc.returncode}."
            raise RuntimeError(f"Falha ao coletar logs QR com --force para {compact_date}: {detail}")

    return {
        "ok": True,
        "produto_id": pid,
        "data": compact_date,
        "executed": True,
        "log_name": expected_name,
        "log_exists": expected_path.exists(),
        "summary": f"Coleta QR executada para {compact_date}.",
        "stdout_tail": "\n".join(stdout.splitlines()[-8:]) if stdout else "",
    }


def load_roteiro_for_product(produto_id: str) -> Dict[str, Any]:
    """Carrega o roteiro para um produto específico."""
    pid = _normalize_product_id(produto_id)
    roteiro_path = get_roteiro_path(pid)
    return load_roteiro(roteiro_path)


def get_tests_payload_for_product(produto_id: str, cnpj: str = None) -> Dict[str, Any]:
    """Obtém os testes disponíveis para um produto.
    
    Se cnpj for fornecido, retorna apenas os testes designados para esse cliente.
    """
    pid = _normalize_product_id(produto_id)
    catalog_by_id = _get_product_catalog_by_id(pid)
    
    tests_list = []
    for test_id, test_info in catalog_by_id.items():
        tests_list.append({
            "id": test_info.get("id"),
            "nome": test_info.get("nome"),
            "descricao": test_info.get("descricao"),
            "objetivo_esperado": test_info.get("objetivo_esperado"),
            "label": f"{test_info.get('id')} - {test_info.get('nome')}",
        })
    
    return {"testes": sorted(tests_list, key=lambda x: x.get("id", ""))}


def _get_product_catalog_by_id(produto_id: str) -> Dict[str, Dict[str, Any]]:
    roteiro = load_roteiro_for_product(produto_id)
    tests = _get_homolog_tests(roteiro)
    out: Dict[str, Dict[str, Any]] = {}
    for tid, test_obj in tests.items():
        normalized_id = str(test_obj.get("id") or tid).zfill(2)
        out[normalized_id] = {
            "id": normalized_id,
            "nome": test_obj.get("nome"),
            "descricao": test_obj.get("descricao"),
            "objetivo_esperado": test_obj.get("objetivo_esperado"),
        }
    return out


def _normalize_client_identifier(value: str, produto_id: str) -> str:
    """Normaliza o identificador do cliente conforme o produto.

    - QR Pago (01): usa CNPJ/identificador normalizado (comportamento atual)
    - Autorizador (02): exige codigo autorizador de 4 digitos numericos
    """
    pid = _normalize_product_id(produto_id)
    raw_value = str(value or "").strip()

    if pid == "02_AutorizadorCARDSE":
        if not re.fullmatch(r"\d{4}", raw_value):
            raise ValueError("Para o produto Autorizador, informe o codigo autorizador com 4 digitos.")
        return raw_value

    return _normalize_cnpj(raw_value)


def _ensure_product_maps(stats: Dict[str, Any]) -> None:
    if not isinstance(stats.get("assigned_tests_by_product"), dict):
        stats["assigned_tests_by_product"] = {}
    if not isinstance(stats.get("tests_by_product"), dict):
        stats["tests_by_product"] = {}


def _get_assigned_tests_for_product(stats: Dict[str, Any], produto_id: str) -> list[str]:
    pid = _normalize_product_id(produto_id)
    _ensure_product_maps(stats)

    by_product = stats.get("assigned_tests_by_product") or {}
    if isinstance(by_product.get(pid), list):
        return [str(item).zfill(2) for item in by_product.get(pid) if str(item).strip()]

    # Compatibilidade: fluxo legado sem segmentacao por produto.
    if pid == "01_QRCARDSE":
        return [str(item).zfill(2) for item in (stats.get("assigned_tests") or []) if str(item).strip()]

    return []


def _set_assigned_tests_for_product(stats: Dict[str, Any], produto_id: str, test_ids: list[str]) -> None:
    pid = _normalize_product_id(produto_id)
    _ensure_product_maps(stats)
    normalized = [str(item).zfill(2) for item in test_ids if str(item).strip()]

    assigned_by_product = stats.get("assigned_tests_by_product") or {}
    assigned_by_product[pid] = normalized
    stats["assigned_tests_by_product"] = assigned_by_product

    if pid == "01_QRCARDSE":
        stats["assigned_tests"] = normalized

    # Mantem sinalizacao global de onboarding usada por endpoints legados.
    stats["onboarding_completed"] = any(bool(v) for v in assigned_by_product.values())


def _get_tests_state_for_product(stats: Dict[str, Any], produto_id: str) -> Dict[str, Any]:
    pid = _normalize_product_id(produto_id)
    _ensure_product_maps(stats)

    tests_by_product = stats.get("tests_by_product") or {}
    product_tests = tests_by_product.get(pid)
    if isinstance(product_tests, dict):
        return dict(product_tests)

    if pid == "01_QRCARDSE":
        return dict(stats.get("tests") or {})

    return {}


def _set_tests_state_for_product(stats: Dict[str, Any], produto_id: str, tests_state: Dict[str, Any]) -> None:
    pid = _normalize_product_id(produto_id)
    _ensure_product_maps(stats)

    tests_by_product = stats.get("tests_by_product") or {}
    tests_by_product[pid] = dict(tests_state or {})
    stats["tests_by_product"] = tests_by_product

    if pid == "01_QRCARDSE":
        stats["tests"] = dict(tests_state or {})


def _compute_product_progress_summary(stats: Dict[str, Any], produto_id: str, total_catalog_tests: int) -> Dict[str, Any]:
    assigned_tests = _get_assigned_tests_for_product(stats, produto_id)
    tests = _get_tests_state_for_product(stats, produto_id)

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


def _build_all_tests_progress_for_product(stats: Dict[str, Any], produto_id: str) -> List[Dict[str, Any]]:
    catalog_by_id = _get_product_catalog_by_id(produto_id)
    tests = _get_tests_state_for_product(stats, produto_id)
    assigned_tests = _get_assigned_tests_for_product(stats, produto_id)
    target_ids = assigned_tests or sorted(tests)
    output: List[Dict[str, Any]] = []

    for test_id in target_ids:
        catalog_item = catalog_by_id.get(test_id) or {}
        if test_id in tests:
            output.append(_build_test_progress_payload(tests[test_id]))
        else:
            output.append(
                _build_test_progress_payload(
                    {
                        "teste_id": str(test_id).zfill(2),
                        "teste_nome": str(catalog_item.get("nome") or "").strip(),
                        "attempts_total": 0,
                        "approved_attempts": 0,
                        "approved_once": False,
                        "attempts_until_approval": None,
                        "last_result": "",
                        "last_attempt_at": "",
                    }
                )
            )

    return output


def enroll_client_tests_for_product(*, cnpj: str, produto_id: str, selected_test_ids: list[str]) -> Dict[str, Any]:
    pid = _normalize_product_id(produto_id)
    normalized_cnpj = _normalize_client_identifier(cnpj, pid)
    catalog_by_id = _get_product_catalog_by_id(pid)
    normalized_ids = sorted({str(item or "").strip().zfill(2) for item in selected_test_ids if str(item or "").strip()})

    if not normalized_ids:
        raise ValueError("Selecione ao menos um teste para homologação.")

    invalid = [item for item in normalized_ids if item not in catalog_by_id]
    if invalid:
        raise ValueError(f"Testes inválidos informados: {', '.join(invalid)}")

    stats = _load_client_stats(normalized_cnpj, pid)
    already_assigned = _get_assigned_tests_for_product(stats, pid)
    if not already_assigned:
        _set_assigned_tests_for_product(stats, pid, normalized_ids)

    saved = _save_client_stats(normalized_cnpj, stats, pid)
    final_assigned = _get_assigned_tests_for_product(saved, pid)
    summary = _compute_product_progress_summary(saved, pid, len(catalog_by_id))
    return {
        "cnpj": normalized_cnpj,
        "assigned_tests": [catalog_by_id[test_id] for test_id in final_assigned if test_id in catalog_by_id],
        "summary": summary,
        "tests": _build_all_tests_progress_for_product(saved, pid),
        "onboarding_required": False,
    }


def get_client_progress_payload_for_product(*, cnpj: str, produto_id: str) -> Dict[str, Any]:
    pid = _normalize_product_id(produto_id)
    normalized_cnpj = _normalize_client_identifier(cnpj, pid)
    stats = _load_client_stats(normalized_cnpj, pid)
    catalog_by_id = _get_product_catalog_by_id(pid)
    assigned_ids = _get_assigned_tests_for_product(stats, pid)
    return {
        "cnpj": normalized_cnpj,
        "onboarding_required": not bool(assigned_ids),
        "assigned_tests": [catalog_by_id[test_id] for test_id in assigned_ids if test_id in catalog_by_id],
        "summary": _compute_product_progress_summary(stats, pid, len(catalog_by_id)),
        "tests": _build_all_tests_progress_for_product(stats, pid),
    }


def get_client_progress_payload_all_products(*, cnpj: str) -> Dict[str, Any]:
    normalized_cnpj = _normalize_cnpj(cnpj)
    produtos = listar_produtos()
    progress_by_product: List[Dict[str, Any]] = []

    for produto in produtos:
        pid = str(produto.get("id") or "")
        if not pid:
            continue
        payload = get_client_progress_payload_for_product(cnpj=normalized_cnpj, produto_id=pid)
        progress_by_product.append(
            {
                "produto": {
                    "id": pid,
                    "nome": str(produto.get("nome") or ""),
                    "descricao": str(produto.get("descricao") or ""),
                    "tipo_validacao": str(produto.get("tipo_validacao") or ""),
                },
                "onboarding_required": bool(payload.get("onboarding_required")),
                "assigned_tests": payload.get("assigned_tests") or [],
                "summary": payload.get("summary") or {},
                "tests": payload.get("tests") or [],
            }
        )

    total_planejados = 0
    total_iniciados = 0
    total_aprovados = 0
    for item in progress_by_product:
        resumo = item.get("summary") or {}
        total_planejados += int(resumo.get("total_testes_planejados") or 0)
        total_iniciados += int(resumo.get("testes_iniciados") or 0)
        total_aprovados += int(resumo.get("testes_aprovados") or 0)

    percentual_geral = round((total_aprovados / total_planejados) * 100, 2) if total_planejados > 0 else 0.0

    return {
        "cnpj": normalized_cnpj,
        "products": progress_by_product,
        "summary": {
            "total_testes_planejados": total_planejados,
            "testes_iniciados": total_iniciados,
            "testes_aprovados": total_aprovados,
            "percentual_aprovacao_geral": percentual_geral,
        },
    }


def list_clients_payload_multiproduct() -> Dict[str, Any]:
    if not CLIENT_HOMOLOG_DIR.is_dir():
        return {"clients": []}

    produtos = listar_produtos()
    produto_meta: Dict[str, Dict[str, Any]] = {}
    for produto in produtos:
        pid_num = str(produto.get("id") or "").zfill(2)
        if not pid_num:
            continue
        produto_meta[_normalize_product_id(pid_num)] = {
            "produto_id": pid_num,
            "produto_nome": str(produto.get("nome") or ""),
        }

    clients_map: Dict[str, Dict[str, Any]] = {}

    def ensure_client_row(cnpj: str) -> Dict[str, Any]:
        if cnpj not in clients_map:
            clients_map[cnpj] = {
                "cnpj": cnpj,
                "products": [],
                "updated_at": "",
            }
        return clients_map[cnpj]

    def append_product_row(client_row: Dict[str, Any], stats: Dict[str, Any], produto_key: str) -> None:
        meta = produto_meta.get(produto_key)
        if not meta:
            return

        catalog_size = len(_get_product_catalog_by_id(produto_key))
        summary = _compute_product_progress_summary(stats, produto_key, catalog_size)
        assigned = _get_assigned_tests_for_product(stats, produto_key)
        tests_state = _get_tests_state_for_product(stats, produto_key)

        # Se não há qualquer informação para o produto, não polui a listagem.
        if not assigned and not tests_state:
            return

        client_row["products"].append(
            {
                "produto_id": meta["produto_id"],
                "produto_nome": meta["produto_nome"],
                "assigned_tests": assigned,
                "onboarding_completed": bool(assigned),
                "summary": summary,
            }
        )

        updated_at = str(stats.get("updated_at") or "")
        if updated_at and updated_at > str(client_row.get("updated_at") or ""):
            client_row["updated_at"] = updated_at

    # Estrutura principal: HOMOLOGACAO_CLIENTES/{produto_key}/{cnpj}/stats.json
    for produto_key in sorted(produto_meta.keys()):
        produto_root = CLIENT_HOMOLOG_DIR / produto_key
        if not produto_root.is_dir():
            continue

        for client_dir in sorted(produto_root.iterdir()):
            if not client_dir.is_dir():
                continue

            cnpj = client_dir.name
            stats = _load_client_stats(cnpj, produto_key)
            client_row = ensure_client_row(cnpj)
            append_product_row(client_row, stats, produto_key)

    # Compatibilidade legada: HOMOLOGACAO_CLIENTES/{cnpj}/stats.json
    for legacy_dir in sorted(CLIENT_HOMOLOG_DIR.iterdir()):
        if not legacy_dir.is_dir():
            continue
        if legacy_dir.name in produto_meta:
            continue
        if not (legacy_dir / "stats.json").is_file():
            continue

        cnpj = legacy_dir.name
        stats = _load_client_stats(cnpj)
        client_row = ensure_client_row(cnpj)
        for produto_key in sorted(produto_meta.keys()):
            append_product_row(client_row, stats, produto_key)

    clients: List[Dict[str, Any]] = []
    for cnpj in sorted(clients_map.keys()):
        row = clients_map[cnpj]
        products = sorted(row.get("products") or [], key=lambda p: str(p.get("produto_id") or ""))
        if not products:
            continue

        total_planejados = sum(int((p.get("summary") or {}).get("total_testes_planejados") or 0) for p in products)
        total_iniciados = sum(int((p.get("summary") or {}).get("testes_iniciados") or 0) for p in products)
        total_aprovados = sum(int((p.get("summary") or {}).get("testes_aprovados") or 0) for p in products)
        percentual_geral = round((total_aprovados / total_planejados) * 100, 2) if total_planejados > 0 else 0.0

        clients.append(
            {
                "cnpj": cnpj,
                "onboarding_completed": any(bool(p.get("onboarding_completed")) for p in products),
                "assigned_tests": [tid for p in products for tid in (p.get("assigned_tests") or [])],
                "total_testes_planejados": total_planejados,
                "testes_iniciados": total_iniciados,
                "testes_aprovados": total_aprovados,
                "percentual_aprovacao_geral": percentual_geral,
                "updated_at": str(row.get("updated_at") or ""),
                "products": products,
            }
        )

    return {"clients": clients}


def admin_set_client_tests_for_product(*, cnpj: str, produto_id: str, selected_test_ids: List[str]) -> Dict[str, Any]:
    pid = _normalize_product_id(produto_id)
    normalized_cnpj = _normalize_client_identifier(cnpj, pid)
    catalog_by_id = _get_product_catalog_by_id(pid)
    normalized_ids = sorted({str(item or "").strip().zfill(2) for item in selected_test_ids if str(item or "").strip()})

    if not normalized_ids:
        raise ValueError("Selecione ao menos um teste.")

    invalid = [item for item in normalized_ids if item not in catalog_by_id]
    if invalid:
        raise ValueError(f"Testes inválidos: {', '.join(invalid)}")

    stats = _load_client_stats(normalized_cnpj, pid)
    _set_assigned_tests_for_product(stats, pid, normalized_ids)
    saved = _save_client_stats(normalized_cnpj, stats, pid)

    summary = _compute_product_progress_summary(saved, pid, len(catalog_by_id))
    return {
        "cnpj": normalized_cnpj,
        "produto_id": pid,
        "assigned_tests": normalized_ids,
        "summary": summary,
    }


def admin_reset_client_onboarding_for_product(*, cnpj: str, produto_id: str) -> Dict[str, Any]:
    pid = _normalize_product_id(produto_id)
    normalized_cnpj = _normalize_client_identifier(cnpj, pid)

    stats = _load_client_stats(normalized_cnpj, pid)
    _set_assigned_tests_for_product(stats, pid, [])

    # Ao resetar onboarding do produto, também limpa o estado de tentativas desse produto.
    _set_tests_state_for_product(stats, pid, {})

    saved = _save_client_stats(normalized_cnpj, stats, pid)
    summary = _compute_product_progress_summary(saved, pid, len(_get_product_catalog_by_id(pid)))
    return {
        "cnpj": normalized_cnpj,
        "produto_id": pid,
        "onboarding_completed": False,
        "summary": summary,
    }


def admin_reset_client_tests_for_product(*, cnpj: str, produto_id: str) -> Dict[str, Any]:
    pid = _normalize_product_id(produto_id)
    normalized_cnpj = _normalize_client_identifier(cnpj, pid)

    stats = _load_client_stats(normalized_cnpj, pid)
    _set_tests_state_for_product(stats, pid, {})
    saved = _save_client_stats(normalized_cnpj, stats, pid)

    summary = _compute_product_progress_summary(saved, pid, len(_get_product_catalog_by_id(pid)))
    return {
        "cnpj": normalized_cnpj,
        "produto_id": pid,
        "tests_reset": True,
        "summary": summary,
    }


def _update_client_stats_for_product(cnpj: str, produto_id: str, teste: Dict[str, Any], is_approved: bool) -> Dict[str, Any]:
    pid = _normalize_product_id(produto_id)
    stats = _load_client_stats(cnpj, pid)
    tests = _get_tests_state_for_product(stats, pid)
    test_id = str(teste.get("id") or "").zfill(2)
    test_name = str(teste.get("nome") or "").strip()

    from datetime import datetime

    now_iso = datetime.now().isoformat(timespec="seconds")
    current = dict(tests.get(test_id) or {})
    attempts_total = int(current.get("attempts_total") or 0) + 1
    approved_attempts = int(current.get("approved_attempts") or 0) + (1 if is_approved else 0)
    approved_once = bool(current.get("approved_once")) or is_approved
    attempts_until_approval = current.get("attempts_until_approval")
    if is_approved and not isinstance(attempts_until_approval, int):
        attempts_until_approval = attempts_total

    updated_entry = {
        "teste_id": test_id,
        "teste_nome": test_name,
        "attempts_total": attempts_total,
        "approved_attempts": approved_attempts,
        "approved_once": approved_once,
        "attempts_until_approval": attempts_until_approval,
        "last_result": "APROVADO" if is_approved else "NEGADO",
        "last_attempt_at": now_iso,
    }
    tests[test_id] = updated_entry
    _set_tests_state_for_product(stats, pid, tests)
    saved = _save_client_stats(cnpj, stats, produto_id)

    return {
        "selected_test": _build_test_progress_payload(updated_entry),
        "all_tests": _build_all_tests_progress_for_product(saved, pid),
        "summary": _compute_product_progress_summary(saved, pid, len(_get_product_catalog_by_id(pid))),
    }


def load_roteiro_for_product(produto_id: str) -> dict:
    """Carrega o roteiro específico do produto."""
    roteiro_path = Path(get_roteiro_path(produto_id))
    
    if not roteiro_path.exists():
        raise FileNotFoundError(f"Roteiro não encontrado: {roteiro_path}")
    
    with open(roteiro_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def get_tests_payload_for_product(produto_id: str, cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Obtém lista de testes para um produto específico.
    
    Se CNPJ é fornecido:
    - Se o cliente JÁ TEM testes designados: retorna apenas os testes designados
    - Se o cliente é NOVO (sem testes designados): retorna TODOS os testes para seleção
    Caso contrário: retorna todos os testes disponíveis do roteiro.
    """
    roteiro = load_roteiro_for_product(produto_id)
    tests = _get_homolog_tests(roteiro)
    
    # Se CNPJ fornecido, verificar se cliente já tem testes designados
    assigned_test_ids = None
    if cnpj:
        cnpj_norm = _normalize_client_identifier(cnpj, produto_id)
        stats = _load_client_stats(cnpj_norm, produto_id)
        assigned_tests = _get_assigned_tests_for_product(stats, produto_id)
        assigned_test_ids = {str(item).zfill(2) for item in assigned_tests if str(item).strip()}
        
        # Só filtrar se o cliente JÁ TEM testes designados
        if not assigned_test_ids:
            # Cliente novo - sem testes designados ainda
            assigned_test_ids = None
    
    out = []
    for tid in sorted(tests.keys()):
        tid_normalized = str(tid).zfill(2)
        
        # Se há testes designados para este cliente, pular os não designados
        if assigned_test_ids is not None and tid_normalized not in assigned_test_ids:
            continue
        
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


def get_api_config_with_products() -> Dict[str, Any]:
    """Configuração da API incluindo lista de produtos."""
    return {
        "base_dir": str(BASE_DIR),
        "logs_dir": str(LOGS_DIR),
        "logs_dir_exists": LOGS_DIR.is_dir(),
        "max_log_size_bytes": MAX_LOG_SIZE_BYTES,
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "produtos": listar_produtos(),
    }


def _build_cardse_evidence(result: Dict[str, Any], log_name: str) -> Dict[str, str]:
    """Gera evidência de homologação para resultados no formato CARDSE (validacoes)."""
    from datetime import datetime

    teste = result.get("teste") or {}
    status = str(result.get("status") or "-")
    resumo_str = str(result.get("resumo") or "-")
    validacoes = result.get("validacoes") or []
    mtis_esperados = result.get("mtis_esperados") or []
    mtis_encontrados = result.get("mtis_encontrados") or []
    erros = result.get("erros") or []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    test_id = str(teste.get("id") or "00").zfill(2)
    test_name = str(teste.get("nome") or "").strip()
    objetivo = str(teste.get("objetivo_esperado") or "-")

    lines: List[str] = []
    lines.append("EVIDENCIA DE HOMOLOGACAO ISO 8583")
    lines.append("=" * 80)
    lines.append(f"Gerado em: {timestamp}")
    lines.append(f"Arquivo de log: {log_name}")
    lines.append(f"Teste: {test_id} - {test_name}")
    lines.append(f"Status geral: {status}")
    lines.append(f"Objetivo esperado: {objetivo}")
    lines.append("")
    lines.append("RESUMO")
    lines.append("-" * 80)
    lines.append(resumo_str)
    lines.append(f"MTIs esperados  : {', '.join(mtis_esperados) or '-'}")
    lines.append(f"MTIs encontrados: {', '.join(mtis_encontrados) or '-'}")
    lines.append(f"Total mensagens validadas: {len(validacoes)}")
    aprovadas = sum(1 for v in validacoes if v.get("aprovado"))
    lines.append(f"Aprovadas: {aprovadas} | Reprovadas: {len(validacoes) - aprovadas}")

    if erros:
        lines.append("")
        lines.append("ERROS")
        lines.append("-" * 80)
        for i, e in enumerate(erros, 1):
            lines.append(f"{i}. {e}")

    lines.append("")
    lines.append("TROCA DE MENSAGENS ISO")
    lines.append("-" * 80)
    for idx, v in enumerate(validacoes, 1):
        mti = str(v.get("mti") or "-")
        direcao = str(v.get("direcao") or "-")
        aprovado = "APROVADO" if v.get("aprovado") else "REPROVADO"
        val_erros = v.get("erros") or []
        campos = v.get("campos") or {}
        
        lines.append(f"MENSAGEM {idx}")
        lines.append(f"  MTI     : {mti}")
        lines.append(f"  Direcao : {direcao}")
        lines.append(f"  Status  : {aprovado}")
        
        # Mostrar campos principais
        if campos:
            campo_itens = []
            for bit_num in sorted(campos.keys(), key=lambda x: int(x) if x.isdigit() else 999):
                valor = str(campos[bit_num] or "")
                campo_itens.append(f"DE{bit_num}={valor}")
            
            if campo_itens:
                lines.append(f"  Campos  : {', '.join(campo_itens)}")
        
        if val_erros:
            lines.append(f"  Erros:")
            for e in val_erros:
                lines.append(f"    - {e}")
        lines.append("")

    content = "\n".join(lines)
    return {"content": content}


def validate_log_payload_with_product(
    *,
    produto_id: str,
    product_type: str = "credito_debito",
    teste_id: str,
    log_name: str,
    de11: str = "",
    de41: str = "",
    cliente: str = "LOCAL",
    comunicacao_tipo: str = "ISO",
    debug: bool = False,
) -> Dict[str, Any]:
    """Valida log usando o validador apropriado para o produto."""
    
    # Validar produto
    try:
        produto = get_produto(produto_id)
    except ValueError as e:
        return {
            "status": "FALHA",
            "resumo": str(e),
            "teste_id": str(teste_id or "").zfill(2),
            "erros": [str(e)],
        }
    
    teste_id = str(teste_id or "").strip()
    if not teste_id:
        raise ValueError("Selecione um teste de homologação.")

    # Ler log
    path = _resolve_log_path(log_name)
    text = _read_log_text(path)
    file_key = _cache_key_for_file(path)
    cache_key = (
        file_key[0],
        file_key[1],
        file_key[2],
        produto_id,
        teste_id,
        str(de11 or ""),
        str(de41 or ""),
        bool(debug),
    )

    # Verificar cache
    with _CACHE_LOCK:
        cached = _VALIDATION_CACHE.get(cache_key)
        if cached is not None:
            cached_result = dict(cached)
            cached_result.setdefault("api_metadata", {})["cached"] = True
            return cached_result

    # Carregar validador apropriado
    validador_info = get_validador_info(produto_id)
    try:
        validador_path = (BASE_DIR / f"{validador_info['module']}.py")
        validador_version_token = str(validador_path.stat().st_mtime_ns) if validador_path.exists() else "0"
        cache_key = (
            file_key[0],
            file_key[1],
            file_key[2],
            produto_id,
            teste_id,
            str(de11 or ""),
            str(de41 or ""),
            bool(debug),
            validador_version_token,
        )

        # Revalidar cache após calcular token da versão do validador.
        with _CACHE_LOCK:
            cached = _VALIDATION_CACHE.get(cache_key)
            if cached is not None:
                cached_result = dict(cached)
                cached_result.setdefault("api_metadata", {})["cached"] = True
                return cached_result

        spec = importlib.util.spec_from_file_location(
            validador_info["module"],
            validador_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Não conseguiu carregar o módulo {validador_info['module']}")
        
        validador_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validador_module)
        validador_func = getattr(validador_module, validador_info["function"])
    except Exception as e:
        return {
            "status": "FALHA",
            "resumo": f"Erro ao carregar validador do produto: {e}",
            "teste_id": str(teste_id or "").zfill(2),
            "erros": [str(e)],
        }

    # Executar validação
    try:
        func_params = inspect.signature(validador_func).parameters
        kwargs: Dict[str, Any] = {
            "teste_id": teste_id,
            "de11": str(de11 or "").strip(),
            "cliente": cliente,
            "debug": debug,
        }
        # Passar roteiro_path correto para o validador carregar o roteiro do produto
        roteiro_path = produto.get("roteiro_path")
        if roteiro_path and "roteiro_path" in func_params:
            kwargs["roteiro_path"] = roteiro_path

        # de41 (QR Pago) ou de42 (Autorizador) — injetar o campo correto conforme produto
        if produto_id == "02":
            # Produto Autorizador: filtro pelo Merchant ID (BIT 42)
            if "de42" in func_params:
                kwargs["de42"] = str(de41 or "").strip()
            # Não passa de41 (Terminal ID não é informado pelo usuário no Autorizador)
        else:
            # Outros produtos (QR Pago, etc): filtro pelo Terminal ID (BIT 41)
            if "de41" in func_params:
                kwargs["de41"] = str(de41 or "").strip()
            # Não passa de42 para QR Pago (não filtra por Merchant ID)
        if "product_type" in func_params:
            kwargs["product_type"] = product_type
        if "comunicacao_tipo" in func_params:
            kwargs["comunicacao_tipo"] = comunicacao_tipo
        result = validador_func(text, **kwargs)
    except Exception as e:
        return {
            "status": "FALHA",
            "resumo": f"Erro durante validação: {e}",
            "teste_id": str(teste_id or "").zfill(2),
            "erros": [str(e)],
        }

    # Decorar resultado apenas se for do validador padrão (tem estrutura "pernas")
    if "pernas" in result and isinstance(result.get("pernas"), list):
        result = _decorate_validation_payload(result)
        if str(result.get("status") or "") == "APROVADO":
            result["evidencia"] = _build_evidence_payload(result, path.name)
        else:
            result["evidencia"] = None
    elif "validacoes" in result:
        # Formato CARDSE: gerar evidência a partir das validacoes
        result["evidencia"] = _build_cardse_evidence(result, path.name)

    result["api_metadata"] = {
        "log_name": path.name,
        "log_size_bytes": file_key[2],
        "produto_id": produto_id,
        "produto_nome": produto.get("nome"),
        "tipo_validacao": produto.get("tipo_validacao"),
        "cached": False,
    }

    if db_store.is_enabled():
        db_store.save_validation_run(
            cnpj=str(cliente or "LOCAL"),
            produto_id=str(produto_id or ""),
            teste_id=teste_id,
            log_name=path.name,
            de11=str(de11 or "").strip(),
            de41=str(de41 or "").strip(),
            status=str(result.get("status") or ""),
            result=result,
        )

    # Cache result
    with _CACHE_LOCK:
        _VALIDATION_CACHE.clear()
        _VALIDATION_CACHE[cache_key] = dict(result)

    return result


def validate_client_payload_with_product(
    *,
    produto_id: str,
    product_type: str = "credito_debito",
    cnpj: str,
    data_teste: str,
    teste_id: str,
    de11: str,
    de41: str,
    comunicacao_tipo: str = "ISO",
) -> Dict[str, Any]:
    """Validação de cliente com suporte a múltiplos produtos."""
    from datetime import datetime
    from services.homolog_service import (
        _parse_test_date,
        _select_log_by_test_date,
        _collect_denied_legs,
    )
    
    # Validar produto
    produto = get_produto(produto_id)
    
    cnpj_norm = _normalize_client_identifier(cnpj, produto_id)
    test_date_iso, _ = _parse_test_date(data_teste)
    stats = _load_client_stats(cnpj_norm, produto_id)
    assigned_tests = set(_get_assigned_tests_for_product(stats, produto_id))

    if not str(teste_id or "").strip():
        raise ValueError("Selecione o teste em homologação.")
    if not str(de11 or "").strip():
        raise ValueError("Informe o Bit 11 (DE11).")
    if not str(de41 or "").strip():
        bit_label = "Bit 42 (DE42 - Merchant ID)" if produto_id == "02" else "Bit 41 (DE41)"
        raise ValueError(f"Informe o {bit_label}.")

    normalized_test_id = str(teste_id or "").strip().zfill(2)
    if not assigned_tests:
        raise ValueError("Primeiro selecione os testes que este cliente ira homologar.")

    if normalized_test_id not in assigned_tests:
        raise ValueError(f"Teste {normalized_test_id} nao foi designado para este cliente.")

    # Executar validação
    log_path = _select_log_by_test_date(test_date_iso, produto_id)
    
    result = validate_log_payload_with_product(
        produto_id=produto_id,
        product_type=product_type,
        teste_id=normalized_test_id,
        log_name=log_path.name,
        de11=de11,
        de41=de41,
        cliente=cnpj_norm,
        comunicacao_tipo=comunicacao_tipo,
    )

    is_approved = str(result.get("status") or "").upper() == "APROVADO"
    denied_legs = _collect_denied_legs(result.get("pernas") or [])
    teste = result.get("teste") or {"id": normalized_test_id, "nome": ""}

    # Gerar record_id simples
    record_id = f"{cnpj_norm}_{normalized_test_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    progress = _update_client_stats_for_product(cnpj_norm, produto_id, teste, is_approved)

    response: Dict[str, Any] = {
        "resultado": "APROVADO" if is_approved else "NEGADO",
        "protocolo": record_id,
        "cnpj": cnpj_norm,
        "teste_id": normalized_test_id,
        "data_teste": test_date_iso,
        "progresso": progress,
    }

    if not is_approved:
        first_denied = denied_legs[0] if denied_legs else {}

        motivos_unicos = []
        seen_motivos = set()
        for denied in denied_legs:
            for msg in denied.get("motivos") or []:
                text = str(msg or "").strip()
                if text and text not in seen_motivos:
                    seen_motivos.add(text)
                    motivos_unicos.append(text)

        # Fallback: alguns validadores reprovam sem preencher "pernas".
        for msg in (result.get("motivos_status_geral") or []):
            text = str(msg or "").strip()
            if text and text not in seen_motivos:
                seen_motivos.add(text)
                motivos_unicos.append(text)

        for msg in (result.get("erros") or []):
            text = str(msg or "").strip()
            if text and text not in seen_motivos:
                seen_motivos.add(text)
                motivos_unicos.append(text)

        blocos_reprovados = result.get("blocos_reprovados") or []
        for bloco in blocos_reprovados:
            if not isinstance(bloco, dict):
                continue
            mti_bloco = str(bloco.get("mti") or "").strip()
            prefixo = f"MTI {mti_bloco}: " if mti_bloco else ""
            for msg in (bloco.get("erros") or []):
                text = str(msg or "").strip()
                if not text:
                    continue
                full_text = f"{prefixo}{text}" if prefixo else text
                if full_text not in seen_motivos:
                    seen_motivos.add(full_text)
                    motivos_unicos.append(full_text)

        if not first_denied and isinstance(blocos_reprovados, list) and blocos_reprovados:
            primeiro_bloco = blocos_reprovados[0] if isinstance(blocos_reprovados[0], dict) else {}
            mti_bloco = str(primeiro_bloco.get("mti") or "").strip()
            first_denied = {
                "perna": f"MTI {mti_bloco}" if mti_bloco else "Perna/Bloco não identificado",
                "motivo": (motivos_unicos[0] if motivos_unicos else "Motivo não identificado"),
            }

        response["perna_negada"] = str(first_denied.get("perna") or "Perna não identificada")
        response["motivo_negacao"] = str(first_denied.get("motivo") or "Motivo não identificado")
        response["pernas_negadas"] = [str(item.get("perna") or "Perna não identificada") for item in denied_legs]
        if not response["pernas_negadas"] and isinstance(blocos_reprovados, list):
            response["pernas_negadas"] = [
                (f"MTI {str(item.get('mti') or '').strip()}" if isinstance(item, dict) and str(item.get("mti") or "").strip() else "Perna/Bloco não identificado")
                for item in blocos_reprovados
            ]
        response["motivos_negacao"] = motivos_unicos if motivos_unicos else ["Motivo não identificado"]

    return response
