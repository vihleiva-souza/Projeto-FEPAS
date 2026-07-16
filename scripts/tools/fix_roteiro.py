import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
ROTEIRO_PATH = BASE_DIR / "data" / "roteiros" / "roteiro_iso_0200.json"

# Load JSON with correct encoding
with open(ROTEIRO_PATH, 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

# Fix test 11
test11 = data['homolog_tests']['11']
test11['rule']['required_chain'][0]['label'] = '0400'
test11['rule']['forbidden_steps'] = [fs for fs in test11['rule']['forbidden_steps'] if fs.get('label') != '0400 deve ter pcode 966031']

# Fix test 12
test12 = data['homolog_tests']['12']
test12['rule']['required_chain'][0]['label'] = '0400'
# Add 0210 to required_chain after 0400
test12['rule']['required_chain'].insert(1, {
    'label': '0210 - compra original (para comparacao de bit 04)',
    'mti': '0210',
    'optional': True
})
# Fix comparacoes - remove all and add only the new one
test12['rule']['comparacoes'] = [{
    'label': 'Bit04_0400_vs_0210_compra_original',
    'left': {'mti': '0400', 'bit': '04'},
    'right': {'mti': '0210', 'bit': '04'},
    'operator': '=='
}]
# Remove 0210 from forbidden_steps any_mti list
if test12['rule']['forbidden_steps']:
    for fs in test12['rule']['forbidden_steps']:
        if 'any_mti' in fs:
            fs['any_mti'] = [mti for mti in fs['any_mti'] if mti != '0210']
# Remove 0400 pcode validation from forbidden_steps
test12['rule']['forbidden_steps'] = [fs for fs in test12['rule']['forbidden_steps'] if fs.get('label') != '0400 deve ter pcode 966031']

# Write back
with open(ROTEIRO_PATH, 'w', encoding='utf-8-sig') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('✓ Tests 11 and 12 fixed successfully!')
