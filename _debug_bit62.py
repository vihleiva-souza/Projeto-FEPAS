import sys
sys.path.insert(0, r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo')
import validador_0200 as v

for fname in ['aud_20260422.txt', 'aud_20260420.txt']:
    path = r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\LOGS de TESTE\\' + fname
    with open(path, encoding='utf-8', errors='replace') as f:
        txt = f.read()
    res = v.validar_log_iso_formatado(txt, filtro_de11='150824', apenas_pernas_interesse=False)
    pernas = res.get('pernas', [])
    print(f'{fname}: total pernas={len(pernas)}')
    for p in pernas:
        bits = p.get('bits') or {}
        b62 = str(bits.get('62', ''))
        partes = b62.split('@', 2)
        apos = partes[2] if len(partes) >= 3 else '(sem segundo @)'
        print(f"  MTI={p.get('mti')} de11={p.get('de11')} | bit62 len={len(b62)} | apos_2at: {repr(apos[:200])}")
