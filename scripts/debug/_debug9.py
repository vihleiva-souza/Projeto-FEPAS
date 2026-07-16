import sys
sys.path.insert(0, r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo')
import validador_0200 as v

with open(r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\LOGS de TESTE\aud_20260420.txt', encoding='utf-8', errors='replace') as f:
    txt = f.read()

res = v.validar_log_iso_formatado(txt, filtro_de11='150824', filtro_de41='SE000001', apenas_pernas_interesse=False)

tx = res.get('transacao_selecionada') or {}
pernas = tx.get('pernas_todas') or tx.get('pernas') or []
print('pernas_todas:', len(pernas))
for i,p in enumerate(pernas):
    if str(p.get('mti') or '') != '0410':
        continue
    t1 = v._extrair_texto_bit62_apos_segundo_arroba(p)
    t2 = v._extrair_texto_id505_bit62(p)
    t3 = v._extrair_id506_bit48_apos_segundo_arroba(p)
    print(f"idx={i} line={p.get('header_line')} mti={p.get('mti')} de03={p.get('de03')}")
    print('  bit62_after2@:', repr(t1[:180]))
    print('  id505_text   :', repr(t2[:180]))
    print('  id506_after2@:', repr(t3[:180]))
