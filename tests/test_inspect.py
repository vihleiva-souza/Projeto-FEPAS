from validador_0200 import load_roteiro
import json
from pathlib import Path

roteiro_path = Path(__file__).resolve().parents[1] / 'data' / 'roteiros' / 'roteiro_iso_0200.json'
roteiro = load_roteiro(str(roteiro_path))

test = roteiro['homolog_tests']['11']
print('Teste 11:')
print(f'  ID: {test.get("id")}')
print(f'  Nome: {test.get("nome")}')
print(f'  Descrição: {test.get("descricao")[:60]}')

rule = test.get('rule', {})
print(f'\nRule - chaves: {list(rule.keys())}')
print(f'Rule keys:')
for key in rule.keys():
    val = rule[key]
    print(f'  {key}: {type(val).__name__}')
    
# Procurar 'pernas' ou similar
if 'pernas' in rule:
    pernas = rule['pernas']
    print(f'\nPernas encontradas: {len(pernas)}')
    if pernas:
        p = pernas[0]
        print(f'Primeira perna - chaves: {list(p.keys())}')
        print(f'MTI: {p.get("mti")}')
        
        bits = p.get('bits', {})
        print(f'Bits type: {type(bits).__name__}')
        
        # Ver primeiros bits
        bit_keys = list(bits.keys())[:10]
        print(f'Primeiras chaves de bits: {bit_keys}')
        
        # Verificar Bit 62
        if '62' in bits:
            print(f'\nBit 62 (chave string) encontrado!')
            print(f'Conteúdo: {str(bits["62"])[:100]}')
        if 62 in bits:
            print(f'Bit 62 (chave int) encontrado!')
            print(f'Conteúdo: {str(bits[62])[:100]}')
