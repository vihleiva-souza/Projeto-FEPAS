#!/usr/bin/env python3
"""
Coletor de audits QR via download HTTP direto.
Funciona em qualquer ambiente (Windows, Linux, macOS) e em Render.

Fluxo (3 estratégias em cascata):
1) Tenta fazer download de aud_YYYYMMDD.txt consolidado da URL
2) Se não existir, lista e baixa .fps.txt individuais já convertidos
3) Se não existir, lista e baixa .fps binários e converte com listafps.exe (Windows)
4) Consolida em um único arquivo: LOGS de TESTE/01_QRCARDSE/aud_YYYYMMDD.txt

Uso:
  python scripts/tools/coletor_audit_qr_http.py
  python scripts/tools/coletor_audit_qr_http.py --date 20260717
  python scripts/tools/coletor_audit_qr_http.py --date 20260717 --force
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
from typing import List, Set, Tuple
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError


URL_AUDIT = (
    "http://k4lc2sewapp0004.producao.softwareexpress.com.br/"
    "logs/fepas-cardse-argentina/006_QRPago/audit/"
)

ARQUIVO_CONTROLE = "dias_procesados_qr.json"
TIMEOUT_DOWNLOAD = 120  # segundos
MAX_RETRIES = 2
CLAVE_FIJA = "0123456789012345"
PARAMETRO_TLV = "tlv[47,48]"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def download_content(url: str, timeout: int = TIMEOUT_DOWNLOAD, retries: int = MAX_RETRIES) -> bytes | None:
    """Faz download com retry automático."""
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=timeout) as response:
                return response.read()
        except HTTPError as e:
            if e.code == 404:
                return None
            if attempt < retries - 1:
                time.sleep(1)
                continue
            raise
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            raise
    return None


def download_html(url: str) -> str:
    """Faz download de página HTML."""
    content = download_content(url)
    if content is None:
        return ""
    return content.decode("utf-8", errors="ignore")


def target_date_yyyymmdd(date_opt: str | None = None) -> str:
    """Formata data para YYYYMMDD."""
    if date_opt:
        date_opt = date_opt.strip()
        dt = datetime.strptime(date_opt, "%Y%m%d")
        return dt.strftime("%Y%m%d")
    return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")


def try_download_consolidated_log(url_base: str, yyyymmdd: str) -> bytes | None:
    """Tenta fazer download do arquivo consolidado aud_YYYYMMDD.txt."""
    consolidated_url = urljoin(url_base, f"aud_{yyyymmdd}.txt")
    print(f"Tentando download consolidado: {consolidated_url}")
    
    content = download_content(consolidated_url)
    if content is not None:
        print(f"[OK] Arquivo consolidado encontrado e baixado ({len(content) / 1024 / 1024:.1f} MB)")
        return content
    
    print(f"[FALHA] Arquivo consolidado nao encontrado")
    return None


def list_fps_txt_for_day(url: str, yyyymmdd: str) -> List[str]:
    """Lista arquivos .fps.txt individuais (já convertidos) para um dia."""
    html = download_html(url)
    if not html:
        return []
    
    # Padrão: aud_YYYYMMDD*.fps.txt (convertidos pelo listafps)
    pattern = rf"aud_{yyyymmdd}\d*\.fps\.txt"
    files = sorted(set(re.findall(pattern, html, flags=re.IGNORECASE)))
    return files


def list_fps_for_day(url: str, yyyymmdd: str) -> List[str]:
    """Lista arquivos .fps binários para um dia."""
    html = download_html(url)
    if not html:
        return []

    # Padrão: aud_YYYYMMDD*.fps (sem .txt - arquivos binários)
    pattern = rf"aud_{yyyymmdd}\d+\.fps(?!\.txt)"
    files = sorted(set(re.findall(pattern, html, flags=re.IGNORECASE)))
    return files


def download_fps_files(
    url_base: str,
    file_names: List[str],
    temp_dir: Path,
) -> List[Path]:
    """Faz download dos arquivos .fps binários."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    downloaded: List[Path] = []

    print(f"Fazendo download de {len(file_names)} arquivos .fps...")
    for i, file_name in enumerate(file_names, 1):
        full_url = urljoin(url_base, file_name)
        destination = temp_dir / file_name

        try:
            content = download_content(full_url)
            if content is not None:
                destination.write_bytes(content)
                downloaded.append(destination)
                print(f"  [{i}/{len(file_names)}] [OK] {file_name} ({len(content) / 1024:.0f} KB)")
            else:
                print(f"  [{i}/{len(file_names)}] [FALHA] {file_name} (404)")
        except Exception as e:
            print(f"  [{i}/{len(file_names)}] [ERRO] {file_name} ({e})")

    return downloaded


def find_listafps_exe(root: Path) -> Path | None:
    """Localiza listafps.exe no projeto."""
    candidates = [
        root / "listafps.exe",
        root / "scripts" / "listafps.exe",
        root / "tools" / "listafps.exe",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def convert_fps_with_listafps(
    listafps_exe: Path,
    fps_file: Path,
    work_dir: Path,
) -> List[Path]:
    """Converte um .fps binário em .fps.txt usando listafps.exe."""
    work_dir.mkdir(parents=True, exist_ok=True)
    temp_fps = work_dir / fps_file.name
    shutil.copy2(str(fps_file), str(temp_fps))

    before = set(work_dir.iterdir())

    cmd = [str(listafps_exe), temp_fps.name, CLAVE_FIJA, PARAMETRO_TLV]
    try:
        subprocess.run(cmd, cwd=str(work_dir), capture_output=True, text=True, shell=False, timeout=60)
    except Exception as e:
        print(f"    [ERRO] listafps falhou em {fps_file.name}: {e}")
        return []

    time.sleep(0.5)
    after = set(work_dir.iterdir())
    generated = [p for p in (after - before) if p.suffix.lower() in (".txt",) or ".fps.txt" in p.name.lower()]

    try:
        temp_fps.unlink(missing_ok=True)
    except OSError:
        pass

    return generated


def download_fps_txt_files(
    url_base: str,
    file_names: List[str],
    temp_dir: Path,
) -> List[Path]:
    """Faz download dos arquivos .fps.txt."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    downloaded: List[Path] = []
    
    print(f"Fazendo download de {len(file_names)} arquivos .fps.txt...")
    for i, file_name in enumerate(file_names, 1):
        full_url = urljoin(url_base, file_name)
        destination = temp_dir / file_name
        
        try:
            content = download_content(full_url)
            if content is not None:
                destination.write_bytes(content)
                downloaded.append(destination)
                print(f"  [{i}/{len(file_names)}] [OK] {file_name} ({len(content) / 1024:.0f} KB)")
            else:
                print(f"  [{i}/{len(file_names)}] [FALHA] {file_name} (404)")
        except Exception as e:
            print(f"  [{i}/{len(file_names)}] [ERRO] {file_name} ({e})")
    
    return downloaded


def consolidate_txt_files(
    txt_files: List[Path],
    yyyymmdd: str,
    output_file: Path,
    source_url: str,
    is_consolidated: bool = False,
) -> Path:
    """Consolida arquivos .txt em um único arquivo."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8", errors="replace") as out:
        out.write("=" * 70 + "\n")
        out.write(f"AUDIT CONSOLIDADO QR - DIA {yyyymmdd}\n")
        out.write(f"Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write(f"URL origem: {source_url}\n")
        if is_consolidated:
            out.write("Origem: Arquivo consolidado da URL\n")
        else:
            out.write("Origem: Consolidação de arquivos .fps.txt individuais\n")
        out.write("=" * 70 + "\n\n")

        if is_consolidated and len(txt_files) == 1:
            # Se foi download direto do consolidado, copia o conteúdo
            out.write(txt_files[0].read_text(encoding="utf-8", errors="replace"))
        else:
            # Consolida múltiplos arquivos
            for file in txt_files:
                out.write("=" * 70 + "\n")
                out.write(f"INICIO ARQUIVO: {file.name}\n")
                out.write("=" * 70 + "\n\n")
                if not file.exists():
                    out.write(f"[AVISO] Arquivo não encontrado: {file}\n")
                else:
                    out.write(file.read_text(encoding="utf-8", errors="replace"))
                out.write("\n\n")
                out.write("=" * 70 + "\n")
                out.write(f"FIM ARQUIVO: {file.name}\n")
                out.write("=" * 70 + "\n\n")

    return output_file


def read_processed_days(control_path: Path) -> Set[str]:
    """Lê dias já processados."""
    if not control_path.exists():
        return set()
    try:
        return set(json.loads(control_path.read_text(encoding="utf-8")))
    except Exception:
        return set()


def write_processed_days(control_path: Path, processed_days: Set[str]) -> None:
    """Escreve dias processados."""
    control_path.parent.mkdir(parents=True, exist_ok=True)
    control_path.write_text(
        json.dumps(sorted(list(processed_days)), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Coletor de audits QR via HTTP (compatível com Render)"
    )
    parser.add_argument(
        "--date",
        help="Dia alvo no formato YYYYMMDD. Se omitido, usa ontem.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocessa o dia mesmo se já estiver em dias_procesados_qr.json.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    root = project_root()
    logs_dir = root / "LOGS de TESTE"
    work_dir = root / "temp" / "qr_audit_http"
    temp_dir = work_dir / "downloads"
    output_dir = work_dir / "saida"
    control_path = output_dir / ARQUIVO_CONTROLE

    logs_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    target_day = target_date_yyyymmdd(args.date)
    processed_days = read_processed_days(control_path)

    print("=" * 70)
    print("COLETA HTTP DE AUDITS QR (sem listafps.exe)")
    print("=" * 70)
    print(f"Dia alvo             : {target_day}")
    print(f"URL audit            : {URL_AUDIT}")
    print(f"Pasta logs do projeto: {logs_dir}")
    print(f"Controle processados : {control_path}")
    print("=" * 70)

    if target_day in processed_days and not args.force:
        print(f"Dia {target_day} ja foi processado. Use --force para reprocessar.")
        return 0

    # ── Estratégia 1: arquivo consolidado ──────────────────────────────────
    consolidated_content = try_download_consolidated_log(URL_AUDIT, target_day)

    if consolidated_content:
        temp_file = temp_dir / f"aud_{target_day}.txt"
        temp_file.write_bytes(consolidated_content)
        txt_files = [temp_file]
        is_consolidated = True

    else:
        # ── Estratégia 2: .fps.txt já convertidos ──────────────────────────
        print(f"\nListando arquivos .fps.txt para {target_day}...")
        fps_txt_files = list_fps_txt_for_day(URL_AUDIT, target_day)

        if fps_txt_files:
            print(f"[OK] Encontrados {len(fps_txt_files)} arquivos .fps.txt")
            txt_files = download_fps_txt_files(URL_AUDIT, fps_txt_files, temp_dir)
            is_consolidated = False

        else:
            # ── Estratégia 3: .fps binários + conversão local com listafps.exe ──
            print(f"[FALHA] Nenhum .fps.txt encontrado")
            print(f"\nListando arquivos .fps binarios para {target_day}...")
            fps_bin_files = list_fps_for_day(URL_AUDIT, target_day)

            if not fps_bin_files:
                print(f"[FALHA] Nenhum arquivo encontrado no servidor para {target_day}")
                return 1

            listafps_exe = find_listafps_exe(root)
            if listafps_exe is None:
                print(f"[FALHA] listafps.exe nao encontrado. Nao e possivel converter .fps binarios.")
                print(f"  Arquivos disponiveis no servidor: {', '.join(fps_bin_files)}")
                print(f"  Coloque listafps.exe na raiz do projeto e tente novamente.")
                return 1

            print(f"[OK] Encontrados {len(fps_bin_files)} arquivos .fps")
            print(f"[OK] Usando listafps.exe: {listafps_exe}")

            fps_work_dir = temp_dir / "listafps_work"
            fps_work_dir.mkdir(parents=True, exist_ok=True)

            downloaded_fps = download_fps_files(URL_AUDIT, fps_bin_files, temp_dir)
            if not downloaded_fps:
                print(f"[FALHA] Nenhum .fps foi baixado com sucesso")
                return 1

            print(f"\nConvertendo {len(downloaded_fps)} arquivos com listafps.exe...")
            txt_files = []
            for i, fps_file in enumerate(downloaded_fps, 1):
                print(f"  [{i}/{len(downloaded_fps)}] Convertendo {fps_file.name}...")
                generated = convert_fps_with_listafps(listafps_exe, fps_file, fps_work_dir)
                if generated:
                    txt_files.extend(generated)
                    print(f"    [OK] Gerou {len(generated)} arquivo(s)")
                else:
                    print(f"    [AVISO] Nenhum arquivo gerado para {fps_file.name}")

            if not txt_files:
                print(f"[FALHA] Nenhum .fps.txt foi gerado pela conversao")
                return 1

            print(f"[OK] {len(txt_files)} arquivos convertidos com sucesso")
            is_consolidated = False

        if not txt_files:
            print(f"[FALHA] Nenhum arquivo disponivel para consolidar")
            return 1

    # QR Pago é produto 01_QRCARDSE
    qr_logs_dir = logs_dir / "01_QRCARDSE"
    consolidated_log = qr_logs_dir / f"aud_{target_day}.txt"
    
    print(f"\nConsolidando em: {consolidated_log}")
    consolidated = consolidate_txt_files(txt_files, target_day, consolidated_log, URL_AUDIT, is_consolidated)
    
    # Log de execução
    daily_log = output_dir / f"audit_qr_{target_day}_log.txt"
    with daily_log.open("w", encoding="utf-8", errors="replace") as f:
        f.write("=" * 70 + "\n")
        f.write("LOG PROCESSO COLETA HTTP QR\n")
        f.write("=" * 70 + "\n")
        f.write(f"Dia processado: {target_day}\n")
        f.write(f"Data execução: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"URL origem: {URL_AUDIT}\n")
        f.write(f"Consolidado: {consolidated}\n")
        f.write(f"Qtd arquivos: {len(txt_files)}\n")
        f.write(f"Tipo coleta: {'Arquivo consolidado' if is_consolidated else 'Arquivos individuais .fps.txt'}\n")
        f.write(f"Tamanho consolidado: {consolidated.stat().st_size / 1024 / 1024:.1f} MB\n")

    processed_days.add(target_day)
    write_processed_days(control_path, processed_days)

    print("\n" + "=" * 70)
    print("[OK] Processo finalizado com sucesso")
    print("=" * 70)
    print(f"Consolidado gerado: {consolidated}")
    print(f"Log de execução   : {daily_log}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
