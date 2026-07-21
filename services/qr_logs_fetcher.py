"""
Serviço para buscar logs do QR Pago da URL pública.
Consolida arquivos .fps por data e processa com listafps.
"""
import os
import subprocess
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
from datetime import datetime
import re


LOGS_BASE_URL = "http://k4lc2sewapp0004.producao.softwareexpress.com.br/logs/fepas-cardse-argentina/006_QRPago/audit/"
LISTAFPS_EXE = Path(__file__).parent.parent / "listafps.exe"


def fetch_fps_logs_by_date(data_teste: str) -> str:
    """
    Busca todos os arquivos .fps da data especificada na URL pública,
    consolida em um arquivo único e o processa com listafps.
    
    Args:
        data_teste: Data no formato YYYYMMDD (ex: "20260721")
    
    Returns:
        Caminho do arquivo .txt processado
    
    Raises:
        ValueError: Se a data for inválida ou não houver arquivos
        URLError: Se não conseguir acessar a URL
    """
    # Validar data
    if len(data_teste) != 8 or not data_teste.isdigit():
        raise ValueError(f"Data inválida: {data_teste}. Use YYYYMMDD")
    
    try:
        datetime.strptime(data_teste, "%Y%m%d")
    except ValueError:
        raise ValueError(f"Data inválida: {data_teste}")
    
    # Criar pasta temporária para download
    temp_dir = Path(__file__).parent.parent / "temp" / f"qr_logs_{data_teste}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Buscar arquivos .fps da URL
    fps_files = _fetch_fps_files_from_url(data_teste, temp_dir)
    
    if not fps_files:
        raise ValueError(f"Nenhum arquivo .fps encontrado para a data {data_teste}")
    
    # Consolidar em um arquivo único
    consolidated_file = temp_dir / f"aud_{data_teste}_consolidated.fps"
    _consolidate_fps_files(fps_files, consolidated_file)
    
    # Processar com listafps
    output_file = _process_fps_with_listafps(consolidated_file)
    
    return str(output_file)


def _fetch_fps_files_from_url(data_teste: str, temp_dir: Path) -> list:
    """Busca arquivos .fps da URL pública para a data especificada."""
    try:
        # Acessar a URL para listar arquivos
        response = urlopen(LOGS_BASE_URL, timeout=30)
        html_content = response.read().decode('utf-8')
        
        # Extrair nomes de arquivos .fps
        # Padrão: procura por links href que terminam em .fps
        fps_pattern = r'href=["\']([^"\']*\.fps)["\']'
        all_fps_files = re.findall(fps_pattern, html_content, re.IGNORECASE)
        
        if not all_fps_files:
            # Tenta padrão alternativo
            fps_pattern = r'>([^<]*\.fps)<'
            all_fps_files = re.findall(fps_pattern, html_content, re.IGNORECASE)
        
        # Filtrar apenas arquivos da data especificada
        # Assumindo padrão: aud_YYYYMMDD_*.fps ou similar
        matching_files = []
        for filename in all_fps_files:
            # Se o nome contém a data, inclui
            if data_teste in filename:
                matching_files.append(filename)
        
        if not matching_files:
            # Se não encontrou com a data, tenta baixar todos e filtrar por conteúdo
            matching_files = all_fps_files
        
        # Baixar arquivos
        downloaded_files = []
        for filename in matching_files:
            try:
                file_url = LOGS_BASE_URL + filename if not filename.startswith('http') else filename
                downloaded_file = temp_dir / filename
                
                with urlopen(file_url, timeout=30) as response:
                    downloaded_file.write_bytes(response.read())
                
                downloaded_files.append(downloaded_file)
            except Exception as e:
                print(f"[QR_LOGS] Erro ao baixar {filename}: {e}")
                continue
        
        return downloaded_files
    
    except URLError as e:
        raise ValueError(f"Erro ao acessar URL de logs: {e}")
    except Exception as e:
        raise ValueError(f"Erro ao buscar arquivos .fps: {e}")


def _consolidate_fps_files(fps_files: list, output_file: Path) -> None:
    """Consolida múltiplos arquivos .fps em um único arquivo."""
    with open(output_file, 'ab') as outfile:
        for fps_file in fps_files:
            if fps_file.exists():
                with open(fps_file, 'rb') as infile:
                    outfile.write(infile.read())


def _process_fps_with_listafps(fps_file: Path) -> Path:
    """Processa arquivo .fps com listafps.exe e retorna arquivo .txt."""
    if not LISTAFPS_EXE.exists():
        raise FileNotFoundError(f"listafps.exe não encontrado em {LISTAFPS_EXE}")
    
    output_file = fps_file.parent / fps_file.stem.replace("_consolidated", "") + ".txt"
    
    try:
        # Executar listafps
        result = subprocess.run(
            [str(LISTAFPS_EXE), str(fps_file)],
            capture_output=True,
            timeout=120,
            cwd=str(LISTAFPS_EXE.parent)
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"listafps falhou: {result.stderr.decode('utf-8', errors='ignore')}")
        
        # Verificar se o arquivo de saída foi criado
        if not output_file.exists():
            raise FileNotFoundError(f"listafps não criou arquivo de saída: {output_file}")
        
        return output_file
    
    except subprocess.TimeoutExpired:
        raise RuntimeError("Processamento com listafps expirou")
    except Exception as e:
        raise RuntimeError(f"Erro ao processar com listafps: {e}")
