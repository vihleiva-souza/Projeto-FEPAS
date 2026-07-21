from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None


def _database_url() -> str:
    return str(os.environ.get("DATABASE_URL") or "").strip()


def is_enabled() -> bool:
    return bool(_database_url() and psycopg2 is not None)


def _connect():
    if psycopg2 is None:
        raise RuntimeError("psycopg2 não está instalado.")
    return psycopg2.connect(_database_url(), connect_timeout=5)


def init_db() -> bool:
    if not is_enabled():
        return False

    ddl = """
    CREATE TABLE IF NOT EXISTS homolog_client_stats (
        id BIGSERIAL PRIMARY KEY,
        cnpj TEXT NOT NULL,
        produto_id TEXT NOT NULL,
        stats_json JSONB NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (cnpj, produto_id)
    );

    CREATE TABLE IF NOT EXISTS homolog_validation_runs (
        id BIGSERIAL PRIMARY KEY,
        cnpj TEXT,
        produto_id TEXT,
        teste_id TEXT,
        log_name TEXT,
        de11 TEXT,
        de41 TEXT,
        status TEXT,
        result_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS homolog_roteiro_submissions (
        id BIGSERIAL PRIMARY KEY,
        submissao_id TEXT UNIQUE,
        cnpj TEXT,
        produto_id TEXT,
        log_name TEXT,
        roteiro_filename TEXT,
        roteiro_content BYTEA,
        result_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[db_store] Falha ao inicializar banco: {exc}")
        return False


def load_client_stats(cnpj: str, produto_id: str) -> Optional[Dict[str, Any]]:
    if not is_enabled():
        return None

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT stats_json
                    FROM homolog_client_stats
                    WHERE cnpj = %s AND produto_id = %s
                    LIMIT 1
                    """,
                    (cnpj, produto_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return dict(row[0] or {})
    except Exception as exc:  # pragma: no cover
        print(f"[db_store] Falha ao carregar stats no banco: {exc}")
        return None


def save_client_stats(cnpj: str, produto_id: str, stats: Dict[str, Any]) -> bool:
    if not is_enabled():
        return False

    try:
        payload = json.dumps(stats, ensure_ascii=False)
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO homolog_client_stats (cnpj, produto_id, stats_json, updated_at)
                    VALUES (%s, %s, %s::jsonb, NOW())
                    ON CONFLICT (cnpj, produto_id)
                    DO UPDATE SET
                        stats_json = EXCLUDED.stats_json,
                        updated_at = NOW()
                    """,
                    (cnpj, produto_id, payload),
                )
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[db_store] Falha ao salvar stats no banco: {exc}")
        return False


def save_validation_run(
    *,
    cnpj: str,
    produto_id: str,
    teste_id: str,
    log_name: str,
    de11: str,
    de41: str,
    status: str,
    result: Dict[str, Any],
) -> bool:
    if not is_enabled():
        return False

    try:
        payload = json.dumps(result, ensure_ascii=False)
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO homolog_validation_runs (
                        cnpj, produto_id, teste_id, log_name, de11, de41, status, result_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (cnpj, produto_id, teste_id, log_name, de11, de41, status, payload),
                )
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[db_store] Falha ao salvar execução no banco: {exc}")
        return False


def save_roteiro_submission(
    *,
    submissao_id: str,
    cnpj: str,
    produto_id: str,
    log_name: str,
    roteiro_filename: str,
    roteiro_content: bytes,
    result: Dict[str, Any],
) -> bool:
    if not is_enabled():
        return False

    try:
        payload = json.dumps(result, ensure_ascii=False)
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO homolog_roteiro_submissions (
                        submissao_id, cnpj, produto_id, log_name,
                        roteiro_filename, roteiro_content, result_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (submissao_id)
                    DO UPDATE SET
                        cnpj = EXCLUDED.cnpj,
                        produto_id = EXCLUDED.produto_id,
                        log_name = EXCLUDED.log_name,
                        roteiro_filename = EXCLUDED.roteiro_filename,
                        roteiro_content = EXCLUDED.roteiro_content,
                        result_json = EXCLUDED.result_json
                    """,
                    (
                        submissao_id,
                        cnpj,
                        produto_id,
                        log_name,
                        roteiro_filename,
                        psycopg2.Binary(roteiro_content or b""),
                        payload,
                    ),
                )
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[db_store] Falha ao salvar submissão de roteiro no banco: {exc}")
        return False


def list_roteiro_submissions() -> list:
    """Retorna lista de submissões de roteiro (sem o conteúdo binário)."""
    if not is_enabled():
        return []
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT submissao_id, cnpj, produto_id, log_name,
                           roteiro_filename, created_at
                    FROM homolog_roteiro_submissions
                    ORDER BY created_at DESC
                    """
                )
                rows = cur.fetchall()
                return [
                    {
                        "submissao_id": r[0],
                        "cnpj": r[1],
                        "produto_id": r[2],
                        "log_name": r[3],
                        "roteiro_filename": r[4],
                        "created_at": r[5].isoformat() if r[5] else None,
                    }
                    for r in rows
                ]
    except Exception as exc:  # pragma: no cover
        print(f"[db_store] Falha ao listar submissões de roteiro: {exc}")
        return []


def get_roteiro_content(submissao_id: str) -> Optional[tuple]:
    """Retorna (roteiro_filename, roteiro_content) para download, ou None se não encontrado."""
    if not is_enabled():
        return None
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT roteiro_filename, roteiro_content
                    FROM homolog_roteiro_submissions
                    WHERE submissao_id = %s
                    LIMIT 1
                    """,
                    (submissao_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return (row[0], bytes(row[1]))
    except Exception as exc:  # pragma: no cover
        print(f"[db_store] Falha ao obter conteúdo do roteiro: {exc}")
        return None