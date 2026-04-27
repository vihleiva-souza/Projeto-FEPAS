import sys
sys.path.insert(0, r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo')
import validador_0200 as v

with open(r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\LOGS de TESTE\aud_20260420.txt', encoding='utf-8', errors='replace') as f:
    txt = f.read()

blocks = v.parse_iso_formatted_blocks(txt)
# Print keys of first block
b0 = blocks[0]
print('Block keys:', list(b0.keys()))
print('Sample block:', {k: str(v)[:80] for k,v in b0.items() if k != 'bits'})

# Search for 150824 in any field
for i, b in enumerate(blocks):
    for k, val in b.items():
        if '150824' in str(val):
            print(f'Found in block {i}, key={k}: {repr(str(val)[:200])}')
            bits = b.get('bits') or {}
            b62 = str(bits.get('62', ''))
            print(f'  mti={b.get("mti")} de11={b.get("de11")} de41={b.get("de41")}')
            print(f'  bit62={repr(b62[:300])}')
            break
