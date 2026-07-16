import sys, json
sys.path.insert(0, r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo')
import validador_0200 as v

with open(r'C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\LOGS de TESTE\aud_20260420.txt', encoding='utf-8', errors='replace') as f:
    txt = f.read()

res = v.avaliar_teste_homologacao_web(txt, teste_id='11', de11='150824', de41='SE000001')
vt = res.get('validacao_teste') or {}
print('status=', res.get('status'))
print('erros=', vt.get('erros'))
print('tipo_info=', json.dumps(vt.get('tipo_info') or {}, ensure_ascii=False, indent=2))
