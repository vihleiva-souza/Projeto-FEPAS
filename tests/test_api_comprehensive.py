#!/usr/bin/env python3
"""Comprehensive API tests for multiproduct feature"""

import urllib.request
import urllib.parse
import json

def test_endpoint(name, method, endpoint, data=None):
    """Test an API endpoint"""
    print(f"\n{'='*60}")
    print(f"Teste: {name}")
    print(f"{'='*60}")
    
    try:
        if method == "GET":
            response = urllib.request.urlopen(f"http://127.0.0.1:5000{endpoint}")
        else:
            encoded_data = urllib.parse.urlencode(data).encode('utf-8') if data else None
            req = urllib.request.Request(f"http://127.0.0.1:5000{endpoint}", data=encoded_data)
            response = urllib.request.urlopen(req)
        
        result = json.loads(response.read().decode('utf-8'))
        print(f"✓ Status HTTP: {response.status}")
        return result
    except urllib.error.HTTPError as e:
        print(f"✗ Erro HTTP {e.code}: {e.reason}")
        try:
            error_data = json.loads(e.read().decode('utf-8'))
            print(f"  Detalhes: {error_data}")
        except:
            pass
        return None

# Test 1: List products
result = test_endpoint(
    "Listar produtos",
    "GET",
    "/api/produtos"
)
if result:
    produtos = result.get("produtos", [])
    print(f"  Produtos: {len(produtos)}")
    for p in produtos:
        print(f"    - {p['id']}: {p['nome']}")

# Test 2: Get tests for Product 01 (QR Pago)
result = test_endpoint(
    "Obter testes - Produto 01 (QR Pago)",
    "GET",
    "/api/produtos/01/tests"
)
if result:
    tests = result.get("tests", [])
    print(f"  Total testes: {len(tests)}")
    for t in tests[:3]:
        print(f"    - {t['id']}: {t['nome']}")

# Test 3: Get tests for Product 02 (Autorizador)
result = test_endpoint(
    "Obter testes - Produto 02 (Autorizador)",
    "GET",
    "/api/produtos/02/tests"
)
if result:
    tests = result.get("tests", [])
    print(f"  Total testes: {len(tests)}")
    for t in tests:
        print(f"    - {t['id']}: {t['nome']}")

# Test 4: Validate with Autorizador CARDSE
result = test_endpoint(
    "Validar com Autorizador (Produto 02)",
    "POST",
    "/api/validate-produto",
    {
        'produto_id': '02',
        'teste_id': '01',
        'log_name': 'aud_20260310_autorizador.txt'
    }
)
if result:
    print(f"  Status: {result.get('status')}")
    print(f"  Resumo: {result.get('resumo')}")
    print(f"  Total pernas: {result.get('total_pernas')}")
    if result.get('api_metadata'):
        print(f"  Produto: {result['api_metadata'].get('produto_nome')}")
        print(f"  Tipo validação: {result['api_metadata'].get('tipo_validacao')}")

# Test 5: Test invalid product
result = test_endpoint(
    "Validar com produto inválido",
    "POST",
    "/api/validate-produto",
    {
        'produto_id': '99',
        'teste_id': '01',
        'log_name': 'aud_20260310_autorizador.txt'
    }
)
if result:
    print(f"  Status: {result.get('status')}")
    print(f"  Resumo: {result.get('resumo')}")

print(f"\n{'='*60}")
print("Todos os testes concluídos!")
print(f"{'='*60}")
