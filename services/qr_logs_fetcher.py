"""
Serviço para buscar logs do QR Pago da URL pública.
Consolida arquivos .fps por data e processa com listafps.
"""
import os
import subprocess
import shutil
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
    print(f"[QR_LOGS] Iniciando busca para data: {data_teste}")
    
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
    print(f"[QR_LOGS] Temp dir criado: {temp_dir}")
    
    # Buscar arquivos .fps da URL
    print(f"[QR_LOGS] Buscando arquivos em: {LOGS_BASE_URL}")
    fps_files = _fetch_fps_files_from_url(data_teste, temp_dir)
    print(f"[QR_LOGS] Arquivos encontrados: {len(fps_files)}")
    
    if not fps_files:
        raise ValueError(f"Nenhum arquivo .fps encontrado para a data {data_teste} em {LOGS_BASE_URL}")
    
    # Consolidar em um arquivo único
    consolidated_file = temp_dir / f"aud_{data_teste}_consolidated.fps"
    print(f"[QR_LOGS] Consolidando arquivos em: {consolidated_file}")
    _consolidate_fps_files(fps_files, consolidated_file)
    print(f"[QR_LOGS] Consolidação concluída")
    
    # Processar com listafps
    print(f"[QR_LOGS] Processando com listafps")
    output_file = _process_fps_with_listafps(consolidated_file)
    print(f"[QR_LOGS] Processamento concluído: {output_file}")
    
    return str(output_file)


def _fetch_fps_files_from_url(data_teste: str, temp_dir: Path) -> list:
    """Busca arquivos .fps da URL pública para a data especificada."""
    try:
        print(f"[QR_LOGS] Conectando a {LOGS_BASE_URL}...")
        # Acessar a URL para listar arquivos
        response = urlopen(LOGS_BASE_URL, timeout=30)
        html_content = response.read().decode('utf-8')
        print(f"[QR_LOGS] HTML recebido: {len(html_content)} bytes")
        
        # Extrair nomes de arquivos .fps
        # Padrão: procura por links href que terminam em .fps
        fps_pattern = r'href=["\']([^"\']*\.fps)["\']'
        all_fps_files = re.findall(fps_pattern, html_content, re.IGNORECASE)
        print(f"[QR_LOGS] Padrão href encontrou: {len(all_fps_files)} arquivos")
        
        if not all_fps_files:
            # Tenta padrão alternativo
            fps_pattern = r'>([^<]*\.fps)<'
            all_fps_files = re.findall(fps_pattern, html_content, re.IGNORECASE)
            print(f"[QR_LOGS] Padrão alternativo encontrou: {len(all_fps_files)} arquivos")
        
        if not all_fps_files:
            print(f"[QR_LOGS] AVISO: Nenhum arquivo .fps encontrado na listagem")
            # Log do HTML para debug
            print(f"[QR_LOGS] HTML sample: {html_content[:500]}")
            return []
        
        # Filtrar apenas arquivos da data especificada
        # Assumindo padrão: aud_YYYYMMDD_*.fps ou similar
        matching_files = []
        for filename in all_fps_files:
            # Se o nome contém a data, inclui
            if data_teste in filename:
                matching_files.append(filename)
                print(f"[QR_LOGS] Arquivo da data encontrado: {filename}")
        
        if not matching_files:
            print(f"[QR_LOGS] AVISO: Nenhum arquivo com data {data_teste} encontrado")
            print(f"[QR_LOGS] Arquivos disponíveis: {all_fps_files[:5]}")  # Mostra primeiros 5
            # Se não encontrou com a data, tenta baixar todos
            matching_files = all_fps_files[:10]  # Limita a 10 para não sobrecarregar
        
        # Baixar arquivos
        downloaded_files = []
        for filename in matching_files:
            try:
                file_url = LOGS_BASE_URL + filename if not filename.startswith('http') else filename
                downloaded_file = temp_dir / filename
                print(f"[QR_LOGS] Baixando: {file_url}")
                
                with urlopen(file_url, timeout=30) as response:
                    content = response.read()
                    downloaded_file.write_bytes(content)
                    print(f"[QR_LOGS] ✓ Baixado: {filename} ({len(content)} bytes)")
                
                downloaded_files.append(downloaded_file)
            except Exception as e:
                print(f"[QR_LOGS] ✗ Erro ao baixar {filename}: {e}")
                continue
        
        print(f"[QR_LOGS] Total baixado: {len(downloaded_files)} arquivos")
        return downloaded_files
    
    except URLError as e:
        print(f"[QR_LOGS] ERRO URLError: {e}")
        raise ValueError(f"Erro ao acessar URL de logs: {e}")
    except Exception as e:
        print(f"[QR_LOGS] ERRO: {e}")
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
    print(f"[QR_LOGS] Verificando listafps em: {LISTAFPS_EXE}")
    
    # Se listafps existe, tenta usar
    if LISTAFPS_EXE.exists():
        output_filename = fps_file.stem.replace("_consolidated", "") + ".txt"
        output_file = fps_file.parent / output_filename
        
        try:
            print(f"[QR_LOGS] Executando listafps.exe...")
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
            
            print(f"[QR_LOGS] listafps.exe concluído com sucesso")
            return output_file
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("Processamento com listafps expirou")
        except Exception as e:
            print(f"[QR_LOGS] AVISO: listafps falhou: {e}")
            # Continua com fallback abaixo
    else:
        print(f"[QR_LOGS] listafps.exe não encontrado. Usando fallback.")
    
    # Fallback: copiar arquivo .fps como .txt (para uso em Linux/Render)
    output_filename = fps_file.stem.replace("_consolidated", "") + ".txt"
    output_file = fps_file.parent / output_filename
    
    print(f"[QR_LOGS] Criando arquivo .txt como fallback: {output_file}")
    shutil.copy2(fps_file, output_file)
    
    if not output_file.exists():
        raise FileNotFoundError(f"Falha ao criar arquivo de saída: {output_file}")
    
    print(f"[QR_LOGS] Arquivo .txt criado via fallback")
    return output_file
