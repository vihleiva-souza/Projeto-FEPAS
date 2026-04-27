import sys
sys.path.insert(0, r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo')
import validador_0200 as v

with open(r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\LOGS de TESTE\aud_20260420.txt', encoding='utf-8', errors='replace') as f:
    txt = f.read()

blocks = v.parse_iso_formatted_blocks(txt)
print('total blocks:', len(blocks))

for b in blocks:
    de11 = str(b.get('de11', ''))
    if de11 == '150824':
        mti = b.get('mti', '')
        bits = b.get('bits') or {}
        b62 = str(bits.get('62', ''))
        partes = b62.split('@', 2)
        apos = partes[2] if len(partes) >= 3 else '(sem segundo @)'
        print(f'MTI={mti} de11={de11}')
        print(f'  bit62 len={len(b62)}')
        print(f'  bit62 raw={repr(b62[:400])}')
        print(f'  apos_2at={repr(apos[:200])}')
