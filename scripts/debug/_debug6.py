import sys
sys.path.insert(0, r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo')
import validador_0200 as v

with open(r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\LOGS de TESTE\aud_20260420.txt', encoding='utf-8', errors='replace') as f:
    txt = f.read()

res = v.avaliar_teste_homologacao_web(txt, teste_id='11', de11='150824', de41='SE000001')

pernas = res.get('pernas', [])
for p in pernas:
    mti = p.get('mti', '')
    if mti in ('0400', '0410'):
        bits = p.get('bits') or {}
        b47 = bits.get('47', '')
        b48 = bits.get('48', '')
        b47_map = p.get('bit47_map') or {}
        print(f'MTI={mti} de03={p.get("de03")}')
        print(f'  bit47 raw={repr(str(b47)[:300])}')
        print(f'  bit47_map (key sample): { {k:v for k,v in list(b47_map.items())[:15]} }')
        print(f'  bit48={repr(str(b48)[:200])}')
        print(f'  ID253={b47_map.get("253","")}  ID283={b47_map.get("283","")}')
