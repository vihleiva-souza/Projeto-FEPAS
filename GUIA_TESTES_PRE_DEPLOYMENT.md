# 🧪 GUIA COMPLETO DE TESTES - PRÉ DEPLOYMENT RENDER

## 📋 Índice
1. Testes Automáticos
2. Testes Manuais
3. Testes de API
4. Checklist Final
5. Troubleshooting

---

## 1️⃣ TESTES AUTOMÁTICOS

### **Opção A: Testes Rápidos (2-3 minutos)**
```bash
cd "c:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo"
python scripts/tools/teste_deploy.py --quick
```

**O que testa:**
- ✓ Ambiente Python
- ✓ Arquivos essenciais
- ✓ Imports do projeto

**Resultado esperado:**
```
✓ Ambiente
✓ Imports
✓ Todos os testes passaram!
```

---

### **Opção B: Testes Completos (5-10 minutos)**
```bash
python scripts/tools/teste_deploy.py --full
```

**O que testa:**
- ✓ Ambiente Python
- ✓ Script de coleta HTTP
- ✓ Imports do projeto
- ✓ Auto-coleta automática
- ✓ Validação completa
- ✓ Database

**Resultado esperado:**
```
✓ Ambiente
✓ Coleta HTTP
✓ Imports
✓ Auto-Coleta
✓ Validação
✓ Database
✓ Resultado: 6/6 passaram!
```

---

### **Opção C: Testes Verbosos (Debug detalhado)**
```bash
python scripts/tools/teste_deploy.py --full --verbose
```

Mostra todas as saídas detalhadas para debugging.

---

## 2️⃣ TESTES MANUAIS

### **Teste 1: Coleta HTTP Manual**

```bash
# Testar coleta de hoje (usa data anterior por padrão)
python scripts/tools/coletor_audit_qr_http.py

# Testar coleta de data específica
python scripts/tools/coletor_audit_qr_http.py --date 20260717

# Forçar recoleta mesmo se já processado
python scripts/tools/coletor_audit_qr_http.py --date 20260717 --force
```

**Verificar resultado:**
```bash
# Verificar se arquivo foi criado
ls "LOGS de TESTE\01_QRCARDSE\aud_20260717.txt"

# Verificar tamanho do arquivo
dir "LOGS de TESTE\01_QRCARDSE\aud_20260717.txt"

# Visualizar conteúdo (primeiras 20 linhas)
type "LOGS de TESTE\01_QRCARDSE\aud_20260717.txt" | more
```

**Esperado:**
- Arquivo criado: `aud_YYYYMMDD.txt`
- Tamanho: 3-15 MB
- Contém: "AUDIT CONSOLIDADO" + dados de transações

**Checklist de Log Válido:**
- [ ] Arquivo tem cabeçalho "AUDIT CONSOLIDADO QR"
- [ ] Contém "aud_202607" (data)
- [ ] Tem múltiplas linhas (>100)
- [ ] Não está vazio

---

### **Teste 2: Auto-Coleta Automática**

```bash
# Python interativo
python

>>> import sys
>>> sys.path.insert(0, r"C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo")
>>> from services.homolog_service import _select_log_by_test_date
>>>
>>> # Remova o arquivo antes de testar
>>> from pathlib import Path
>>> test_file = Path(r"LOGS de TESTE\01_QRCARDSE\aud_20260716.txt")
>>> if test_file.exists():
>>>     test_file.unlink()
>>>     print("Arquivo removido para teste")
>>>
>>> # Agora teste a auto-coleta
>>> path = _select_log_by_test_date("20260716", "01_QRCARDSE")
>>> print(f"✓ Log encontrado: {path.name}")
>>>
>>> # Verifique se arquivo foi criado
>>> print(f"Arquivo existe? {test_file.exists()}")
>>> print(f"Tamanho: {test_file.stat().st_size / 1024 / 1024:.1f} MB")
```

**Esperado:**
```
ℹ [LOG AUTO-COLETA] Log não encontrado para 20260716...
ℹ [LOG AUTO-COLETA] ✓ Coleta bem-sucedida para 20260716
✓ Log encontrado: aud_20260716.txt
Arquivo existe? True
Tamanho: 8.5 MB
```

**O que deve acontecer:**
1. Sistema detecta que log não existe
2. Dispara `coletor_audit_qr_http.py --date 20260716`
3. Faz download da URL
4. Consolida em arquivo
5. Retorna o arquivo para usar

---

### **Teste 3: Validação Completa**

```bash
python

>>> import sys
>>> sys.path.insert(0, r"C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo")
>>> from services.homolog_service_multiproduct import validate_log_payload_with_product
>>>
>>> # Testar validação
>>> result = validate_log_payload_with_product(
...     produto_id="01_QRCARDSE",
...     teste_id="01",
...     log_name="aud_20260717.txt",
...     de11="",
...     de41="",
... )
>>>
>>> print(f"Status: {result.get('status')}")
>>> print(f"Resumo: {result.get('resumo')}")
```

**Esperado:**
```
Status: APROVADO
Resumo: Teste 01 validado com sucesso...
```

---

## 3️⃣ TESTES DE API

### **Teste 4: Iniciar Servidor Local**

```bash
# Terminal 1: Inicie o servidor
python app_homolog_web.py

# Esperado:
# WARNING in app.run(): This is a development server. Do not use it in production.
# Running on http://127.0.0.1:5000
```

### **Teste 5: Endpoints da API**

**Terminal 2: Testar endpoints**

```bash
# Test 1: Health Check
curl http://localhost:5000/

# Esperado: HTML da home page

# Test 2: List Logs
curl http://localhost:5000/api/logs

# Esperado:
# {
#   "logs": [...],
#   "total": N
# }

# Test 3: Get API Config
curl http://localhost:5000/api/config

# Esperado:
# {
#   "base_dir": "...",
#   "logs_dir": "...",
#   "produtos": [...]
# }
```

### **Teste 6: Validação via API**

```bash
# Testar coleta automática via API
curl -X POST http://localhost:5000/api/produtos/01_QRCARDSE/logs/fetch-by-date \
  -H "Content-Type: application/json" \
  -d '{"data_teste": "20260717", "force": false}'

# Esperado:
# {
#   "ok": true,
#   "executed": true,
#   "log_exists": true,
#   "summary": "Coleta QR executada para 20260717."
# }
```

---

## 4️⃣ CHECKLIST FINAL

Antes de fazer push para Render, verifique:

### **Código**
- [ ] Script `coletor_audit_qr_http.py` criado
- [ ] `_select_log_by_test_date()` modificado com auto-coleta
- [ ] `fetch_logs_for_product_by_date()` usa novo script
- [ ] Sem erros de syntax (`python -m py_compile scripts/tools/coletor_audit_qr_http.py`)

### **Testes Locais**
- [ ] Testes automáticos passam (`python scripts/tools/teste_deploy.py --full`)
- [ ] Coleta HTTP manual funciona
- [ ] Auto-coleta automática funciona
- [ ] Validação retorna resultados

### **Arquivos**
- [ ] `LOGS de TESTE/01_QRCARDSE/` existe
- [ ] `LOGS de TESTE/02_AutorizadorCARDSE/` existe
- [ ] `temp/qr_audit_http/` criado após testes

### **Render Config**
- [ ] `render.yaml` configurado com Render Disk
- [ ] `HOMOLOG_LOGS_DIR=/var/data` definido (se necessário)
- [ ] `requirements.txt` atualizado (se houver novos pacotes)

### **Variáveis de Ambiente**
```bash
# Configurar em Render Dashboard:
HOMOLOG_LOGS_DIR = /var/data/logs
HOMOLOG_SECRET_KEY = (valor seguro)
```

### **URLs**
- [ ] URL de audit server acessível: http://k4lc2sewapp0004...

---

## 5️⃣ TROUBLESHOOTING

### **Erro: "Nenhum log encontrado para a data YYYYMMDD"**

**Solução:**
```bash
# 1. Verificar se URL está acessível
python -c "from urllib.request import urlopen; print(urlopen('http://k4lc2sewapp0004.producao.softwareexpress.com.br/logs/fepas-cardse-argentina/006_QRPago/audit/').status)"

# 2. Testar script de coleta manualmente
python scripts/tools/coletor_audit_qr_http.py --date 20260717

# 3. Verificar logs de execução
dir temp/qr_audit_http/saida/
type temp/qr_audit_http/saida/audit_qr_20260717_log.txt
```

---

### **Erro: "Timeout during download"**

**Solução:**
```bash
# Aumentar timeout em coletor_audit_qr_http.py
# Linha 23: TIMEOUT_DOWNLOAD = 180  # aumentar de 120

# Ou usar --force para retentar
python scripts/tools/coletor_audit_qr_http.py --date 20260717 --force
```

---

### **Erro: "Module not found"**

**Solução:**
```bash
# Verificar imports
python -c "import services.homolog_service; print('OK')"
python -c "import services.homolog_service_multiproduct; print('OK')"

# Instalar dependências
pip install -r requirements.txt
```

---

### **Erro: "Permission denied" (no Render)

**Solução no render.yaml:**
```yaml
disks:
  - name: homolog-logs
    mountPath: /var/data
    
buildCommand: mkdir -p /var/data/logs /var/data/LOGS\ de\ TESTE/01_QRCARDSE
```

---

## 📊 MATRIZ DE TESTES

| Teste | Tempo | Crítico? | Comando |
|-------|-------|----------|---------|
| Ambiente | <1min | ✓ | `python scripts/tools/teste_deploy.py --quick` |
| Coleta HTTP | 5-30s | ✓ | `python scripts/tools/coletor_audit_qr_http.py --date 20260717` |
| Imports | <1min | ✓ | `python -c 'import services.homolog_service'` |
| Auto-Coleta | 30s | ✓ | Teste manual em Python |
| Validação | 10s | ✓ | Teste manual em Python |
| Database | <1min | ✗ | Teste automático |
| API | 5-10min | ✓ | `curl` commands |

---

## 🚀 FLUXO DE TESTES RECOMENDADO

### **Primeira Vez (Setup)**
```bash
# 1. Testes rápidos
python scripts/tools/teste_deploy.py --quick

# 2. Coleta manual
python scripts/tools/coletor_audit_qr_http.py --date 20260717

# 3. Testes completos
python scripts/tools/teste_deploy.py --full

# 4. Testar API localmente
python app_homolog_web.py
# Em outro terminal:
curl http://localhost:5000/
```

### **Antes de Each Commit**
```bash
python scripts/tools/teste_deploy.py --quick
```

### **Antes de Deploy no Render**
```bash
python scripts/tools/teste_deploy.py --full
# + Verificar checklist acima
# + Fazer commit e push
```

---

## ✅ PRONTO PARA RENDER?

Se todos os testes passarem:

```bash
git add .
git commit -m "feat: Auto-coleta QR com script HTTP compatible com Render"
git push origin main
```

Render detectará o push automaticamente e iniciará o deploy! 🚀

---

## 📞 CONTATO / SUPORTE

Se tiver problemas:
1. Revisar logs em `temp/qr_audit_http/saida/`
2. Executar testes com `--verbose`
3. Verificar URL da API: `http://k4lc2sewapp0004...`
4. Confirmar Python 3.9+

---

**Data**: 20/07/2026  
**Versão**: 1.0  
**Status**: ✅ Pronto para Deploy
