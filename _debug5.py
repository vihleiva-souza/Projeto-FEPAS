import sys
sys.path.insert(0, r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo')
import validador_0200 as v

with open(r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\LOGS de TESTE\aud_20260420.txt', encoding='utf-8', errors='replace') as f:
    txt = f.read()

res = v.avaliar_teste_homologacao_web(txt, teste_id='11', de11='150824', de41='SE000001')

# Find perna 0410
pernas = res.get('pernas', [])
print(f'Test status: {res.get("status")}')
print(f'Total pernas: {len(pernas)}')
for p in pernas:
    mti = p.get('mti', '')
    bits = p.get('bits') or {}
    b62 = str(bits.get('62', ''))
    partes = b62.split('@', 2)
    apos = partes[2] if len(partes) >= 3 else '(sem segundo @)'
    print(f'  MTI={mti} de03={p.get("de03")}')
    print(f'    bit62 len={len(b62)} raw={repr(b62[:300])}')
    print(f'    apos_2at={repr(apos[:200])}')

print('\nErros:', res.get('erros', []))
