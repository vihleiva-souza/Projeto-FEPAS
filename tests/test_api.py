#!/usr/bin/env python3
"""Quick API endpoint tests"""

import urllib.request
import json

endpoints = [
    'http://127.0.0.1:5000/api/produtos/01/tests',
    'http://127.0.0.1:5000/api/produtos/02/tests',
]

for url in endpoints:
    try:
        print('\n' + '='*60)
        print(f'Testando: {url}')
        print('='*60)
        response = urllib.request.urlopen(url)
        data = json.loads(response.read().decode('utf-8'))
        tests = data.get('tests', [])
        print(f'Total de testes: {len(tests)}')
        for test in tests[:3]:
            test_id = test.get('id')
            test_nome = test.get('nome')
            print(f'  - Teste {test_id}: {test_nome}')
        if len(tests) > 3:
            print(f'  ... e mais {len(tests) - 3} testes')
    except Exception as e:
        print(f'Erro: {e}')
        import traceback
        traceback.print_exc()
