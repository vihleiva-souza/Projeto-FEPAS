import sys
sys.path.insert(0, r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo')
import validador_0200 as v

with open(r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\LOGS de TESTE\aud_20260420.txt', encoding='utf-8', errors='replace') as f:
    txt = f.read()

blocks = v.parse_iso_formatted_blocks(txt)
for i,b in enumerate(blocks):
    raw = str(b.get('raw_iso') or '')
    if '150824' in raw and raw.startswith('0010000410'):
        fields = b.get('fields') or {}
        tlv_map = b.get('tlv_map') or {}
        print('idx', i)
        print('raw head', raw[:180])
        print('field keys', sorted(list(fields.keys()))[:30], '... total', len(fields))
        print('has 48?', '48' in fields, 'has 62?', '62' in fields)
        print('tlv_map keys', tlv_map.keys())
        print('tlv_map bit48 keys sample', list((tlv_map.get('48') or {}).keys())[:10])
        print('tlv_map bit62 keys sample', list((tlv_map.get('62') or {}).keys())[:10])
        print('bit48 506 from tlv_map:', repr(str((tlv_map.get('48') or {}).get('506',''))[:220]))
        print('bit62 505 from tlv_map:', repr(str((tlv_map.get('62') or {}).get('505',''))[:220]))
        break
