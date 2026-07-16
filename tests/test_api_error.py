#!/usr/bin/env python3
"""Test API endpoint with error handling"""

import urllib.request
import urllib.parse
import json

data = urllib.parse.urlencode({
    'produto_id': '02',
    'teste_id': '01', 
    'log_name': 'aud_20260310_autorizador.txt'
}).encode('utf-8')

try:
    req = urllib.request.Request('http://127.0.0.1:5000/api/validate-produto', data=data)
    response = urllib.request.urlopen(req)
    result = json.loads(response.read().decode('utf-8'))
    print('SUCCESS - Status:', result.get('status'))
    print('Resumo:', result.get('resumo'))
    print('Total pernas:', result.get('total_pernas'))
except urllib.error.HTTPError as e:
    print(f'HTTP Error {e.code}: {e.reason}')
    error_body = e.read().decode('utf-8')
    print('Response body:')
    print(error_body[:1000])
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
