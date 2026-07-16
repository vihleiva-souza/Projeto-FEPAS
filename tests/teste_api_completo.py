#!/usr/bin/env python3
import urllib.request
import json
import urllib.parse

print('=' * 70)
print('TESTE 1: Verificar listagem de produtos')
print('=' * 70)
try:
    response = urllib.request.urlopen('http://127.0.0.1:5000/api/produtos')
    data = json.loads(response.read().decode('utf-8'))
    print(f'✓ Status: {response.status}')
    print(f'✓ Produtos encontrados: {len(data.get("produtos", []))}')
    for p in data.get('produtos', []):
        print(f'  - Produto {p.get("id")}: {p.get("nome")} ({p.get("tipo_validacao")})')
except Exception as e:
    print(f'✗ Erro: {e}')

print()
print('=' * 70)
print('TESTE 2: Carregar testes QR Pago (Produto 01)')
print('=' * 70)
try:
    response = urllib.request.urlopen('http://127.0.0.1:5000/api/produtos/01/tests')
    data = json.loads(response.read().decode('utf-8'))
    print(f'✓ Status: {response.status}')
    print(f'✓ Testes carregados: {len(data.get("tests", []))}')
    tests = data.get('tests', [])
    if tests:
        print('✓ Primeiros 3 testes:')
        for t in tests[:3]:
            print(f'  - {t.get("test_id")}: {t.get("test_name")}')
except Exception as e:
    print(f'✗ Erro: {e}')

print()
print('=' * 70)
print('TESTE 3: Carregar testes Autorizador (Produto 02)')
print('=' * 70)
try:
    response = urllib.request.urlopen('http://127.0.0.1:5000/api/produtos/02/tests')
    data = json.loads(response.read().decode('utf-8'))
    print(f'✓ Status: {response.status}')
    print(f'✓ Testes carregados: {len(data.get("tests", []))}')
    tests = data.get('tests', [])
    if tests:
        print('✓ Testes do Autorizador:')
        for t in tests[:5]:
            print(f'  - {t.get("test_id")}: {t.get("test_name")}')
except Exception as e:
    print(f'✗ Erro: {e}')

print()
print('=' * 70)
print('TESTE 4: Validação com Produto 01 (QR Pago)')
print('=' * 70)
try:
    data = urllib.parse.urlencode({
        'produto_id': '01',
        'teste_id': '01',
        'log_name': 'aud_20260310.txt',
        'de11': '123456',
        'de41': 'MERCHANT',
        'cliente': 'TEST_CLIENT'
    }).encode('utf-8')
    
    req = urllib.request.Request('http://127.0.0.1:5000/api/validate-produto', data=data)
    response = urllib.request.urlopen(req)
    result = json.loads(response.read().decode('utf-8'))
    print(f'✓ Status: {response.status}')
    print(f'✓ Resultado: {result.get("status")}')
    print(f'✓ Total de mensagens: {result.get("total_pernas", "N/A")}')
except Exception as e:
    print(f'✗ Erro: {e}')

print()
print('=' * 70)
print('✅ TESTES DE API EXECUTADOS!')
print('=' * 70)
