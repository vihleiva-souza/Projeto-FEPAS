import sys
sys.path.insert(0, r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo')
import validador_0200 as v

with open(r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\LOGS de TESTE\aud_20260420.txt', encoding='utf-8', errors='replace') as f:
    txt = f.read()

res = v.validar_log_iso_formatado(txt, filtro_de11='150824', filtro_de41='SE000001')
print('erros:', res.get('erros'))
print('resumo:', res.get('resumo'))

# pernas podem estar em transacao_selecionada ou transacoes
ts = res.get('transacao_selecionada')
if ts:
    pernas = ts.get('pernas', [])
else:
    pernas = [p for t in res.get('transacoes', []) for p in t.get('pernas', [])]

print(f'pernas encontradas: {len(pernas)}')
for p in pernas:
    mti = p.get('mti', '')
    bits = p.get('bits') or {}
    b62 = str(bits.get('62', ''))
    partes = b62.split('@', 2)
    apos = partes[2] if len(partes) >= 3 else '(sem segundo @)'
    print(f'  MTI={mti} de11={p.get("de11")} de41={p.get("de41")}')
    print(f'    bit62 len={len(b62)} raw={repr(b62[:400])}')
    print(f'    apos_2at={repr(apos[:200])}')
