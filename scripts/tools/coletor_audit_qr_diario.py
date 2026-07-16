#!/usr/bin/env python3
"""
Coletor diario de audits QR Pago (dia anterior por padrao).

Fluxo:
1) Lista na URL os .fps do dia alvo (YYYYMMDD).
2) Baixa cada .fps para pasta temporaria.
3) Executa listafps.exe com parametro tlv[47,48].
4) Consolida todos os .txt gerados em um unico arquivo:
   LOGS de TESTE/aud_YYYYMMDD_qr.txt
5) Move os arquivos individuais para pasta de backup local.

Uso:
  python scripts/tools/coletor_audit_qr_diario.py
  python scripts/tools/coletor_audit_qr_diario.py --date 20260705
  python scripts/tools/coletor_audit_qr_diario.py --force
  python scripts/tools/coletor_audit_qr_diario.py --listafps-dir "C:/caminho/da/pasta"
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple
from urllib.parse import urljoin
from urllib.request import Request, urlopen


URL_AUDIT = (
    "http://k4lc2sewapp0004.producao.softwareexpress.com.br/"
    "logs/fepas-cardse-argentina/006_QRPago/audit/"
)

NOME_EXE = "listafps.exe"
CLAVE_FIJA = "0123456789012345"
PARAMETRO_TLV = "tlv[47,48]"
ARQUIVO_CONTROLE = "dias_procesados_qr.json"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_listafps_dir(root: Path) -> Path:
    return root


def download_html(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as response:
        content = response.read()
    return content.decode("utf-8", errors="ignore")


def target_date_yyyymmdd(date_opt: str | None = None) -> str:
    if date_opt:
        date_opt = date_opt.strip()
        dt = datetime.strptime(date_opt, "%Y%m%d")
        return dt.strftime("%Y%m%d")
    return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")


def list_audits_for_day(url: str, yyyymmdd: str) -> List[str]:
    html = download_html(url)
    pattern = rf"aud_{yyyymmdd}\d+\.fps"
    files = re.findall(pattern, html, flags=re.IGNORECASE)
    return sorted(set(files))


def download_audit(url_base: str, file_name: str, download_dir: Path) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    destination = download_dir / file_name
    full_url = urljoin(url_base, file_name)
    req = Request(full_url, headers={"User-Agent": "Mozilla/5.0"})

    with urlopen(req, timeout=120) as response:
        with destination.open("wb") as f:
            shutil.copyfileobj(response, f)

    return destination


def list_current_files(folder: Path) -> Dict[str, Dict[str, object]]:
    out: Dict[str, Dict[str, object]] = {}
    for item in folder.iterdir():
        if item.is_file():
            stat = item.stat()
            out[item.name] = {
                "path": item,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
            }
    return out


def detect_generated_files(
    before: Dict[str, Dict[str, object]],
    after: Dict[str, Dict[str, object]],
    temp_fps: Path,
) -> List[Path]:
    generated: List[Path] = []

    for name, info_after in after.items():
        path_after = info_after["path"]
        if not isinstance(path_after, Path):
            continue

        if name.lower() == NOME_EXE.lower():
            continue
        if path_after.resolve() == temp_fps.resolve():
            continue

        if name not in before:
            generated.append(path_after)
            continue

        info_before = before[name]
        if (
            info_after["mtime"] != info_before["mtime"]
            or info_after["size"] != info_before["size"]
        ):
            generated.append(path_after)

    return generated


def run_listafps(
    listafps_exe: Path,
    listafps_dir: Path,
    original_fps: Path,
) -> Tuple[bool, List[Path], str, str]:
    temp_fps = listafps_dir / original_fps.name
    shutil.copy2(str(original_fps), str(temp_fps))

    before = list_current_files(listafps_dir)

    cmd = [
        str(listafps_exe),
        temp_fps.name,
        CLAVE_FIJA,
        PARAMETRO_TLV,
    ]

    result = subprocess.run(
        cmd,
        cwd=str(listafps_dir),
        capture_output=True,
        text=True,
        shell=False,
    )

    time.sleep(1)

    after = list_current_files(listafps_dir)
    generated = detect_generated_files(before, after, temp_fps)

    try:
        if temp_fps.exists():
            temp_fps.unlink()
    except OSError:
        pass

    return (result.returncode == 0, generated, result.stdout or "", result.stderr or "")


def read_processed_days(control_path: Path) -> Set[str]:
    if not control_path.exists():
        return set()
    try:
        return set(json.loads(control_path.read_text(encoding="utf-8")))
    except Exception:
        return set()


def write_processed_days(control_path: Path, processed_days: Set[str]) -> None:
    control_path.parent.mkdir(parents=True, exist_ok=True)
    control_path.write_text(
        json.dumps(sorted(list(processed_days)), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def consolidate_txt_files(
    txt_files: List[Path],
    yyyymmdd: str,
    output_file: Path,
    source_url: str,
) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8", errors="replace") as out:
        out.write("=" * 70 + "\n")
        out.write(f"AUDIT CONSOLIDADO QR - DIA {yyyymmdd}\n")
        out.write(f"Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write(f"URL origem: {source_url}\n")
        out.write(f"Parametro TLV: {PARAMETRO_TLV}\n")
        out.write("=" * 70 + "\n\n")

        for file in txt_files:
            out.write("=" * 70 + "\n")
            out.write(f"INICIO ARQUIVO: {file.name}\n")
            out.write("=" * 70 + "\n\n")
            if not file.exists():
                out.write(f"[AVISO] Arquivo nao encontrado no momento da consolidacao: {file}\n")
            else:
                out.write(file.read_text(encoding="utf-8", errors="replace"))
            out.write("\n\n")
            out.write("=" * 70 + "\n")
            out.write(f"FIM ARQUIVO: {file.name}\n")
            out.write("=" * 70 + "\n\n")

    return output_file


def move_generated_to_backup(generated_files: List[Path], backup_dir: Path) -> List[Path]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    moved: List[Path] = []

    for source in generated_files:
        if not source.exists():
            continue

        destination = backup_dir / source.name
        if destination.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = backup_dir / f"{source.stem}_{stamp}{source.suffix}"

        shutil.move(str(source), str(destination))
        moved.append(destination)

    return moved


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coletor diario de audits QR")
    parser.add_argument(
        "--date",
        help="Dia alvo no formato YYYYMMDD. Se omitido, usa ontem.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocessa o dia mesmo se ja estiver em dias_procesados_qr.json.",
    )
    parser.add_argument(
        "--listafps-dir",
        help="Pasta onde esta o listafps.exe (padrao: raiz do projeto).",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    root = project_root()
    logs_dir = root / "LOGS de TESTE"
    work_dir = root / "temp" / "qr_audit_ingest"
    download_dir = work_dir / "downloads"
    output_dir = work_dir / "saida"
    control_path = output_dir / ARQUIVO_CONTROLE

    listafps_dir = Path(args.listafps_dir).resolve() if args.listafps_dir else default_listafps_dir(root)
    listafps_exe = listafps_dir / NOME_EXE

    if not listafps_dir.exists():
        print(f"ERRO: pasta do listafps nao existe: {listafps_dir}")
        return 1
    if not listafps_exe.exists():
        print(f"ERRO: executavel nao encontrado: {listafps_exe}")
        return 1

    logs_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    target_day = target_date_yyyymmdd(args.date)
    processed_days = read_processed_days(control_path)

    print("=" * 70)
    print("COLETA DIARIA DE AUDITS QR")
    print("=" * 70)
    print(f"Dia alvo             : {target_day}")
    print(f"URL audit            : {URL_AUDIT}")
    print(f"Pasta listafps       : {listafps_dir}")
    print(f"Executavel           : {listafps_exe}")
    print(f"Pasta logs do projeto: {logs_dir}")
    print(f"Controle processados : {control_path}")
    print("=" * 70)

    if target_day in processed_days and not args.force:
        print(f"Dia {target_day} ja foi processado. Use --force para reprocessar.")
        return 0

    audits = list_audits_for_day(URL_AUDIT, target_day)
    if not audits:
        print(f"Nenhum .fps encontrado para {target_day} na URL informada.")
        return 0

    print(f"Arquivos .fps encontrados ({len(audits)}):")
    for name in audits:
        print(f"  - {name}")

    generated_all: List[Path] = []
    run_logs: List[Dict[str, object]] = []

    for audit_name in audits:
        try:
            downloaded = download_audit(URL_AUDIT, audit_name, download_dir)
            ok, generated, stdout, stderr = run_listafps(listafps_exe, listafps_dir, downloaded)
            run_logs.append(
                {
                    "arquivo": audit_name,
                    "ok": ok,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
            if ok:
                generated_all.extend(generated)
            else:
                print(f"Falha ao processar: {audit_name}")
        except Exception as exc:
            run_logs.append(
                {
                    "arquivo": audit_name,
                    "ok": False,
                    "stdout": "",
                    "stderr": str(exc),
                }
            )
            print(f"Erro inesperado em {audit_name}: {exc}")

    # Dedup por caminho e mantém apenas arquivos ainda existentes para consolidar.
    unique_txt: Dict[str, Path] = {}
    for p in generated_all:
        if p.suffix.lower() == ".txt":
            unique_txt[str(p.resolve())] = p
    txt_files = sorted([p for p in unique_txt.values() if p.exists()], key=lambda p: p.name)

    if not txt_files:
        print("Nenhum .txt gerado para consolidar.")
        return 1

    # QR Pago é produto 01_QRCARDSE - logs salvos em LOGS de TESTE/01_QRCARDSE/
    qr_logs_dir = logs_dir / "01_QRCARDSE"
    consolidated_log = qr_logs_dir / f"aud_{target_day}.txt"
    consolidated = consolidate_txt_files(txt_files, target_day, consolidated_log, URL_AUDIT)

    backup_dir = output_dir / f"individuais_{target_day}"
    moved_files = move_generated_to_backup(generated_all, backup_dir)

    daily_log = output_dir / f"audit_qr_{target_day}_log.txt"
    with daily_log.open("w", encoding="utf-8", errors="replace") as f:
        f.write("=" * 70 + "\n")
        f.write("LOG PROCESSO DIARIO QR\n")
        f.write("=" * 70 + "\n")
        f.write(f"Dia processado: {target_day}\n")
        f.write(f"Data execucao: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"URL origem: {URL_AUDIT}\n")
        f.write(f"Consolidado: {consolidated}\n")
        f.write(f"Qtd FPS: {len(audits)}\n")
        f.write(f"Qtd TXT: {len(txt_files)}\n")
        f.write(f"Qtd movidos backup: {len(moved_files)}\n\n")

        f.write("FPS PROCESSADOS\n")
        f.write("-" * 70 + "\n")
        for item in run_logs:
            f.write(f"Arquivo: {item['arquivo']} | OK: {item['ok']}\n")

        f.write("\nARQUIVOS MOVIDOS\n")
        f.write("-" * 70 + "\n")
        for m in moved_files:
            f.write(str(m) + "\n")

    processed_days.add(target_day)
    write_processed_days(control_path, processed_days)

    print("\nProcesso finalizado com sucesso.")
    print(f"Consolidado gerado: {consolidated}")
    print(f"Log de execucao   : {daily_log}")
    print(f"Backup individual : {backup_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
