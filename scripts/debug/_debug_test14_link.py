import sys
sys.path.insert(0, r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo')
import validador_0200 as v

with open(r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\LOGS de TESTE\aud_20260420.txt', encoding='utf-8', errors='replace') as f:
    txt = f.read()

# Exemplo: entrada por cancelamento (0400)
res = v.avaliar_teste_homologacao_web(txt, teste_id='14', de11='150824', de41='SE000001')
pernas = res.get('pernas') or []

mtis = [str(p.get('mti') or '') for p in pernas]
print('total_pernas:', len(pernas))
print('tem_0400:', any(m == '0400' for m in mtis))
print('tem_0200:', any(m == '0200' for m in mtis))
print('mtis_unicos:', sorted(set(mtis)))

# Mostra algumas pernas-chave para inspeção
for p in pernas:
    mti = str(p.get('mti') or '')
    if mti in {'0200', '0400', '0410', '0210'}:
        print(f"mti={mti} de03={p.get('de03')} de11={p.get('de11')} de41={p.get('de41')}")
