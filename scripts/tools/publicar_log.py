#!/usr/bin/env python3
"""
Publica arquivos de log de auditoria no servidor Render (ou local).

A pasta local e alimentada externamente. Este script apenas faz o upload
dos arquivos para o servidor de destino (local ou producao Render).

Produtos suportados:
  01_QRCARDSE          -> LOGS de TESTE/01_QRCARDSE/aud_YYYYMMDD.txt
  02_AutorizadorCARDSE -> LOGS de TESTE/02_AutorizadorCARDSE/aud_YYYYMMDD.txt

Uso:
  # Publicar um produto no Render
  python scripts/tools/publicar_log.py --produto 01_QRCARDSE --date 20260720 --url https://seu-app.onrender.com --key SUA_CHAVE

  # Publicar os dois produtos de uma vez
  python scripts/tools/publicar_log.py --todos --date 20260720 --url https://seu-app.onrender.com --key SUA_CHAVE

  # Publicar ontem (ambos produtos)
  python scripts/tools/publicar_log.py --todos --ontem --url https://seu-app.onrender.com --key SUA_CHAVE

  # Testar localmente (sem --url, usa localhost)
  python scripts/tools/publicar_log.py --todos --date 20260528
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

if sys.stdout.encoding and sys.stdout.encoding.lower() == "cp1252":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PRODUTOS = {
    "01_QRCARDSE": "01_QRCARDSE",
    "02_AutorizadorCARDSE": "02_AutorizadorCARDSE",
    "01": "01_QRCARDSE",
    "02": "02_AutorizadorCARDSE",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_log(root: Path, produto_id: str, yyyymmdd: str) -> Path | None:
    path = root / "LOGS de TESTE" / produto_id / f"aud_{yyyymmdd}.txt"
    return path if path.exists() else None


def upload_log(url_base: str, produto_id: str, yyyymmdd: str, log_file: Path, admin_key: str = "") -> dict:
    """Envia o arquivo de log para o endpoint admin do servidor."""
    endpoint = f"{url_base.rstrip('/')}/api/admin/logs/upload"
    boundary = "----PublicarLogBoundary"

    def field(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n"
            f"{value}\r\n"
        ).encode("utf-8")

    parts: list[bytes] = [
        field("produto_id", produto_id),
        field("data_teste", yyyymmdd),
    ]
    if admin_key:
        parts.append(field("admin_key", admin_key))

    file_header = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"log_file\"; filename=\"{log_file.name}\"\r\n"
        f"Content-Type: text/plain\r\n\r\n"
    ).encode("utf-8")

    body = b"".join(parts) + file_header + log_file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    if admin_key:
        headers["X-Admin-Key"] = admin_key

    req = Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body_err)
        except Exception:
            return {"error": f"HTTP {e.code}: {body_err[:300]}"}


def publicar(root: Path, produto_id: str, yyyymmdd: str, url: str, key: str) -> bool:
    log_file = find_log(root, produto_id, yyyymmdd)

    if log_file is None:
        print(f"  [AVISO] Arquivo nao encontrado: LOGS de TESTE/{produto_id}/aud_{yyyymmdd}.txt -- pulando")
        return False

    size_mb = log_file.stat().st_size / 1024 / 1024
    print(f"  Arquivo : {log_file.name}  ({size_mb:.1f} MB)")
    print(f"  Enviando para {url}...")

    result = upload_log(url, produto_id, yyyymmdd, log_file, key)

    if result.get("success"):
        print(f"  [OK] {result.get('message')}  ({result.get('size_mb')} MB no servidor)")
        return True
    else:
        print(f"  [ERRO] {result.get('error', result)}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Publica logs de auditoria no servidor")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--produto", choices=list(PRODUTOS.keys()), help="Produto especifico")
    group.add_argument("--todos", action="store_true", help="Publica os dois produtos")

    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument("--date", help="Data no formato YYYYMMDD")
    date_group.add_argument("--ontem", action="store_true", help="Usa a data de ontem")

    parser.add_argument("--url", default="http://127.0.0.1:5000", help="URL base do servidor (padrao: localhost:5000)")
    parser.add_argument("--key", default="", help="HOMOLOG_ADMIN_KEY do Render. Vazio para local.")
    args = parser.parse_args()

    yyyymmdd = (
        (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        if args.ontem
        else args.date.replace("-", "").replace("/", "")
    )

    produtos_alvo = (
        ["01_QRCARDSE", "02_AutorizadorCARDSE"]
        if args.todos
        else [PRODUTOS[args.produto]]
    )

    root = project_root()

    print("=" * 60)
    print("PUBLICACAO DE LOGS DE AUDITORIA")
    print("=" * 60)
    print(f"Data     : {yyyymmdd}")
    print(f"Produtos : {', '.join(produtos_alvo)}")
    print(f"Servidor : {args.url}")
    print(f"Auth key : {'[configurada]' if args.key else '[sem autenticacao - local]'}")
    print("=" * 60)

    resultados: dict[str, bool] = {}
    for pid in produtos_alvo:
        print(f"\n[{pid}]")
        resultados[pid] = publicar(root, pid, yyyymmdd, args.url, args.key)

    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    for pid, ok in resultados.items():
        status = "[OK]   " if ok else "[FALHA]"
        print(f"  {status}  {pid}")
    print("=" * 60)

    return 0 if all(resultados.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
