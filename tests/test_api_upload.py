import requests
import json

# Configuração
API_URL = "http://localhost:5000"
CNPJ = "00047118230855"
PRODUTO_ID = "02"

# Teste 1: Verificar se API está rodando
try:
    resp = requests.get(f"{API_URL}/api/health", timeout=5)
    print(f"✅ API Status: {resp.status_code}")
except Exception as e:
    print(f"❌ API não está respondendo: {e}")
    print("   Inicie com: python app_homolog_web.py")
    exit(1)

# Teste 2: Upload de roteiro via API
print(f"\n📤 Enviando roteiro para validação...")

files = {
    'roteiro_file': open('data/roteiros/roteiro_temp.docx', 'rb')
}

data = {
    'cnpj': CNPJ,
    'log_name': 'aud_20260304.txt',
    'produto_id': PRODUTO_ID,
    'testes_selecionados': '[3, 14, 15]'
}

try:
    resp = requests.post(
        f"{API_URL}/api/validar-roteiro-cliente-batch",
        files=files,
        data=data,
        timeout=30
    )
    
    print(f"✅ Resposta: {resp.status_code}")
    resultado = resp.json()
    
    print(f"\n📊 Resultado:")
    print(f"   Status: {resultado.get('status')}")
    print(f"   Submissão ID: {resultado.get('submissao_id')}")
    print(f"   Taxa de sucesso: {resultado.get('resumo', {}).get('percentual_sucesso')}%")
    print(f"   Testes: {resultado.get('resumo', {}).get('aprovados')}/{resultado.get('resumo', {}).get('validados')} aprovados")
    
    # Verificar se arquivos foram salvos
    from pathlib import Path
    submissao_id = resultado.get('submissao_id')
    timestamp = submissao_id.split('_')[1] + '_' + submissao_id.split('_')[2]
    pasta = Path(f"data/clientes/{CNPJ}/submissoes/{timestamp}")
    
    print(f"\n✅ Verificando arquivos salvos em {pasta.name}:")
    for arquivo in pasta.glob('*'):
        print(f"   ✅ {arquivo.name} ({arquivo.stat().st_size} bytes)")
        
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
finally:
    files['roteiro_file'].close()
