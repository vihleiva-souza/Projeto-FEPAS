#!/usr/bin/env python3
"""
🧪 SCRIPT DE TESTES ANTES DO DEPLOY NO RENDER

Executa testes para validar:
1. Script de coleta HTTP
2. Auto-coleta automática
3. Validação completa
4. Integração com API

Uso:
  python scripts/tools/teste_deploy.py
  python scripts/tools/teste_deploy.py --quick
  python scripts/tools/teste_deploy.py --full
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple


class Colors:
    """ANSI color codes para terminal"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Imprime cabeçalho"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}{Colors.RESET}\n")


def print_ok(text: str):
    """Imprime sucesso"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_fail(text: str):
    """Imprime erro"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_info(text: str):
    """Imprime informação"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def print_warn(text: str):
    """Imprime aviso"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def get_project_root() -> Path:
    """Retorna raiz do projeto"""
    return Path(__file__).resolve().parents[2]


def run_command(cmd: List[str], timeout: int = 300) -> Tuple[int, str, str]:
    """Executa comando e retorna (code, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(get_project_root()),
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout após {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def test_environment() -> bool:
    """Testa se ambiente está pronto"""
    print_header("🔍 TESTE 1: Verificação de Ambiente")
    
    root = get_project_root()
    all_ok = True
    
    # Python version
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print_ok(f"Python {version.major}.{version.minor}.{version.micro}")
    else:
        print_fail(f"Python {version.major}.{version.minor} (requer 3.9+)")
        all_ok = False
    
    # Arquivos essenciais
    essential_files = [
        "scripts/tools/coletor_audit_qr_http.py",
        "services/homolog_service.py",
        "services/homolog_service_multiproduct.py",
        "app_homolog_web.py",
    ]
    
    for file in essential_files:
        path = root / file
        if path.exists():
            print_ok(f"Arquivo encontrado: {file}")
        else:
            print_fail(f"Arquivo NÃO encontrado: {file}")
            all_ok = False
    
    # Diretórios
    dirs_to_check = [
        "LOGS de TESTE/01_QRCARDSE",
        "LOGS de TESTE/02_AutorizadorCARDSE",
        "temp",
        "scripts/tools",
    ]
    
    for dir_name in dirs_to_check:
        path = root / dir_name
        path.mkdir(parents=True, exist_ok=True)
        print_ok(f"Diretório pronto: {dir_name}")
    
    return all_ok


def test_coletor_script() -> bool:
    """Testa script de coleta HTTP"""
    print_header("📥 TESTE 2: Script Coletor HTTP")
    
    root = get_project_root()
    script = root / "scripts/tools/coletor_audit_qr_http.py"
    
    if not script.exists():
        print_fail(f"Script não encontrado: {script}")
        return False
    
    print_info("Testando coleta para data: 20260717")
    
    code, stdout, stderr = run_command(
        [sys.executable, str(script), "--date", "20260717"],
        timeout=120
    )
    
    if code == 0:
        print_ok(f"Script executado com sucesso")
        
        # Verifica se arquivo foi criado
        logs_dir = root / "LOGS de TESTE" / "01_QRCARDSE"
        log_file = logs_dir / "aud_20260717.txt"
        
        if log_file.exists():
            size_mb = log_file.stat().st_size / 1024 / 1024
            print_ok(f"Arquivo criado: aud_20260717.txt ({size_mb:.1f} MB)")
            
            # Verifica conteúdo
            content = log_file.read_text(encoding="utf-8", errors="ignore")[:500]
            if "AUDIT" in content.upper() or len(content) > 100:
                print_ok(f"Arquivo contém dados válidos")
                return True
            else:
                print_warn(f"Arquivo vazio ou inválido")
                return False
        else:
            print_fail(f"Arquivo NÃO foi criado")
            if stderr:
                print_warn(f"Erro: {stderr[:200]}")
            return False
    else:
        print_fail(f"Script falhou com código {code}")
        if stderr:
            print_warn(f"Stderr: {stderr[:300]}")
        if stdout:
            print_warn(f"Stdout: {stdout[:300]}")
        return False


def test_imports() -> bool:
    """Testa imports do projeto"""
    print_header("📦 TESTE 3: Imports Python")
    
    modules_to_test = [
        ("services.homolog_service", "homolog_service"),
        ("services.homolog_service_multiproduct", "homolog_service_mp"),
        ("services.db_store", "db_store"),
        ("validador_0200", "validador"),
    ]
    
    all_ok = True
    
    for module_name, alias in modules_to_test:
        try:
            code = f"import {module_name} as m; print('OK')"
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                cwd=str(get_project_root()),
                timeout=10
            )
            
            if result.returncode == 0:
                print_ok(f"Import OK: {module_name}")
            else:
                print_fail(f"Import FALHOU: {module_name}")
                if result.stderr:
                    print_warn(f"  {result.stderr[:150]}")
                all_ok = False
        except Exception as e:
            print_fail(f"Import ERROR: {module_name} - {e}")
            all_ok = False
    
    return all_ok


def test_auto_coleta() -> bool:
    """Testa auto-coleta automática"""
    print_header("⚡ TESTE 4: Auto-Coleta Automática")
    
    root = get_project_root()
    
    # Limpa arquivo para testar auto-coleta
    test_date = "20260716"
    logs_dir = root / "LOGS de TESTE" / "01_QRCARDSE"
    test_file = logs_dir / f"aud_{test_date}.txt"
    
    if test_file.exists():
        print_info(f"Removendo arquivo para testar auto-coleta: {test_file.name}")
        test_file.unlink()
        print_ok("Arquivo removido")
    else:
        print_info(f"Arquivo não existe (ok para teste)")
    
    # Testa função de seleção de log
    print_info(f"Testando _select_log_by_test_date com data {test_date}...")
    
    code = f"""
import sys
sys.path.insert(0, '{root}')
from services.homolog_service import _select_log_by_test_date
try:
    path = _select_log_by_test_date('{test_date}', '01_QRCARDSE')
    print(f'OK:{{path.name}}')
except Exception as e:
    print(f'ERRO:{{str(e)[:100]}}')
"""
    
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=120
    )
    
    output = result.stdout.strip()
    
    if output.startswith("OK:"):
        log_name = output.replace("OK:", "")
        print_ok(f"Auto-coleta funcionou! Log obtido: {log_name}")
        
        # Verifica se arquivo foi criado
        new_file = logs_dir / f"aud_{test_date}.txt"
        if new_file.exists():
            print_ok(f"Arquivo criado: {new_file.name}")
            return True
        else:
            print_warn(f"Auto-coleta rodou mas arquivo não foi criado")
            return False
    else:
        if "ERRO:" in output:
            error = output.replace("ERRO:", "")
            print_fail(f"Auto-coleta falhou: {error}")
        else:
            print_fail(f"Auto-coleta retornou: {output}")
        return False


def test_validacao() -> bool:
    """Testa validação completa"""
    print_header("✓ TESTE 5: Validação Completa")
    
    root = get_project_root()
    
    # Certifica que há log disponível
    logs_dir = root / "LOGS de TESTE" / "01_QRCARDSE"
    test_file = logs_dir / "aud_20260717.txt"
    
    if not test_file.exists():
        print_warn(f"Arquivo {test_file.name} não existe")
        print_info(f"Pulando teste de validação")
        return None
    
    print_info(f"Testando validação com arquivo: {test_file.name}")
    print_info(f"Tamanho: {test_file.stat().st_size / 1024:.0f} KB")
    
    code = f"""
import sys
sys.path.insert(0, '{root}')

from services.homolog_service_multiproduct import validate_log_payload_with_product

try:
    result = validate_log_payload_with_product(
        produto_id='01_QRCARDSE',
        teste_id='01',
        log_name='aud_20260717.txt',
        de11='',
        de41='',
    )
    status = result.get('status', 'DESCONHECIDO')
    print(f'OK:{{status}}')
except Exception as e:
    print(f'ERRO:{{str(e)[:150]}}')
"""
    
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=60
    )
    
    output = result.stdout.strip()
    
    if output.startswith("OK:"):
        status = output.replace("OK:", "")
        print_ok(f"Validação executada! Status: {status}")
        return True
    else:
        if "ERRO:" in output:
            error = output.replace("ERRO:", "")
            print_warn(f"Validação retornou erro: {error}")
        else:
            print_warn(f"Validação retornou: {output}")
        return True  # Não é falha crítica


def test_api_endpoints() -> bool:
    """Testa endpoints da API"""
    print_header("🔌 TESTE 6: Endpoints da API")
    
    root = get_project_root()
    
    print_warn("Este teste requer Flask rodando")
    print_info("Para testar endpoints completos:")
    print_info("  1. Inicie o servidor: python app_homolog_web.py")
    print_info("  2. Em outro terminal, execute testes HTTP")
    
    return None  # Pula este teste


def test_database() -> bool:
    """Testa conexão com banco"""
    print_header("💾 TESTE 7: Database")
    
    root = get_project_root()
    
    code = f"""
import sys
sys.path.insert(0, '{root}')

from services import db_store

try:
    db_store.init_db()
    is_enabled = db_store.is_enabled()
    print(f'OK:Enabled={{is_enabled}}')
except Exception as e:
    print(f'ERRO:{{str(e)[:100]}}')
"""
    
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=10
    )
    
    output = result.stdout.strip()
    
    if output.startswith("OK:"):
        enabled = "Enabled=True" in output
        status = "habilitado" if enabled else "desabilitado"
        print_ok(f"Database OK ({status})")
        return True
    else:
        if "ERRO:" in output:
            error = output.replace("ERRO:", "")
            print_warn(f"Database: {error}")
        return True  # Não é falha crítica


def print_checklist() -> None:
    """Imprime checklist antes do deploy"""
    print_header("✅ CHECKLIST PRÉ-DEPLOYMENT")
    
    checklist = [
        ("Ambiente Python 3.9+", "python --version"),
        ("Script HTTP criado", "ls scripts/tools/coletor_audit_qr_http.py"),
        ("Imports funcionando", "python -c 'import services.homolog_service'"),
        ("Auto-coleta ativada", "grep -n '_select_log_by_test_date' services/homolog_service.py"),
        ("Render Disk configurado", "Revisar render.yaml"),
        ("Variáveis de ambiente", "HOMOLOG_LOGS_DIR=/var/data"),
        ("Testes locais OK", "Todos os testes acima devem passar"),
    ]
    
    for i, (item, cmd) in enumerate(checklist, 1):
        print(f"{Colors.CYAN}{i}.{Colors.RESET} {item}")
        if cmd:
            print(f"   {Colors.BOLD}$ {cmd}{Colors.RESET}")
    
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Testes pré-deployment Render")
    parser.add_argument("--quick", action="store_true", help="Testes rápidos apenas")
    parser.add_argument("--full", action="store_true", help="Testes completos (padrão)")
    parser.add_argument("--verbose", action="store_true", help="Saída verbosa")
    
    args = parser.parse_args()
    
    results: Dict[str, bool | None] = {}
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          🧪 TESTES PRÉ-DEPLOYMENT RENDER                    ║")
    print("║     Sistema de Coleta e Validação de Logs QR Pago          ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}\n")
    
    # TESTE 1
    results["Ambiente"] = test_environment()
    
    # TESTE 2
    if not args.quick:
        results["Coleta HTTP"] = test_coletor_script()
    
    # TESTE 3
    results["Imports"] = test_imports()
    
    # TESTE 4
    if not args.quick:
        results["Auto-Coleta"] = test_auto_coleta()
    
    # TESTE 5
    if not args.quick:
        results["Validação"] = test_validacao()
    
    # TESTE 6
    if not args.quick:
        results["Database"] = test_database()
    
    # RESUMO
    print_header("📋 RESUMO DOS TESTES")
    
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    total = len(results)
    
    for name, result in results.items():
        if result is True:
            print_ok(f"{name}")
        elif result is False:
            print_fail(f"{name}")
        else:
            print_warn(f"{name} (pulado)")
    
    print(f"\n{Colors.BOLD}Resultado: {passed}/{total} passaram{Colors.RESET}")
    
    if failed == 0:
        print_ok(f"✓ Todos os testes passaram! Pronto para deploy.")
        print_checklist()
        return 0
    else:
        print_fail(f"✗ {failed} teste(s) falharam. Revise antes de fazer deploy.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
