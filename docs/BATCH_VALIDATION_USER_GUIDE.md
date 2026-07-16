# DUAL-MODE VALIDATION SYSTEM - USER GUIDE

## 🎯 OVERVIEW

The system now supports **two validation modes**:

1. **Manual Mode** (existing) - Validate one test at a time
2. **Automatic Mode** (new) - Validate multiple tests via Word roteiro upload

Both modes work simultaneously. Clients can choose which fits their workflow best.

---

## 📖 MODE 1: MANUAL VALIDATION (Test-by-Test)

**When to use:** Debugging specific tests, validating one test at a time

**How it works:**
1. Client selects a test ID (e.g., "14 - Desfazimento")
2. Client provides BIT 11 (STAN) and BIT 42 (Merchant ID)
3. Client selects log file to validate against
4. System validates single test and returns detailed results

**Endpoint:** `POST /api/validate-produto`

**Form Parameters:**
```
teste_id: "14"              # Test ID
de11: "040011"              # BIT 11 (STAN)
de42: "077698017000199"     # BIT 42 (Merchant ID)
log_name: "aud_20260304.txt"# Log file name
produto_id: "02"            # Product (01=QR Pago, 02=CARDSE)
```

**Response:** Detailed per-leg validation results
```json
{
  "status": "APROVADO|REPROVADO",
  "aprovado": true/false,
  "motivos_status_geral": [...],
  "pernas": [
    {
      "mti": "0200",
      "status": "APROVADO",
      ...
    },
    {
      "mti": "0210",
      "status": "APROVADO",
      ...
    }
  ]
}
```

---

## 📄 MODE 2: AUTOMATIC BATCH VALIDATION (Roteiro Upload)

**When to use:** Complete homologation testing, validating entire roteiro at once

**How it works:**
1. Client prepares roteiro Word file (v1.9+) with test data
2. Client fills in "Evidências dos Testes" column:
   ```
   Resultado: OK
   Data/Hora: 04/03 14:25
   BIT 11: 040011
   BIT 42: 077698017000199
   ```
3. Client uploads roteiro + selects log file
4. System extracts all tests and validates each
5. Returns batch results with summary

**Endpoint:** `POST /api/validar-roteiro-cliente-batch`

**Form Parameters (multipart/form-data):**
```
roteiro_file:    [Word .docx file]     # Required: Client roteiro
log_name:        "aud_20260304.txt"    # Required: Log file name
produto_id:      "02"                  # Optional: Product ID
```

**Example cURL:**
```bash
curl -X POST http://localhost:5000/api/validar-roteiro-cliente-batch \
  -F "roteiro_file=@Roteiro_Cliente_1.9.docx" \
  -F "log_name=aud_20260304.txt" \
  -F "produto_id=02"
```

**Response:** Batch validation results
```json
{
  "status": "SUCESSO|PARCIAL|FALHA",
  "timestamp": "2026-07-15T14:30:00",
  "log_name": "aud_20260304.txt",
  "produto_id": "02",
  "arquivo_resultado": "batch_resultados_20260715_143000.json",
  "resumo": {
    "total": 3,
    "aprovados": 2,
    "reprovados": 1,
    "percentual_sucesso": 66.67
  },
  "resultados": [
    {
      "teste_id": 14,
      "status": "APROVADO",
      "bit11": "040011",
      "bit42": "077698017000199",
      "cadeia": "0200, 0210, 0420, 0430",
      "pernas_totais": 4,
      "pernas_aprovadas": 4
    },
    {
      "teste_id": 15,
      "status": "REPROVADO",
      "bit11": "040014",
      "bit42": "077698017000199",
      "motivo": "Mensagem 0202 não encontrada",
      "pernas_totais": 0,
      "pernas_aprovadas": 0
    },
    ...
  ]
}
```

---

## 📋 ROTEIRO WORD FILE FORMAT

### Required Structure
- **File type:** Word (.docx)
- **Version:** 1.9+ (Roteiro de Homologação FepasCardSE_Cartão - Versão Cliente)
- **Table:** Must contain "Sequência de testes" table

### Column "Evidências dos Testes"
Fill in format (one per line):
```
Resultado: <test result or OK>
Data/Hora: <transaction date/time>
BIT 11: <STAN value - 6 digits>
BIT 42: <Merchant ID - 15 characters>
```

### Important Rules
- ✅ **Only complete tests** (with all 4 fields filled) will be validated
- ✅ Empty tests are automatically skipped
- ✅ Multiple formats accepted (e.g., "Data/Hora da transação" also works)
- ✅ Whitespace and formatting variations handled automatically

### Example Row in Roteiro
```
Teste 14 (Desfazimento):
  Resultado: OK
  Data/Hora: 04/03 14:25
  BIT 11: 040011
  BIT 42: 077698017000199
  
Teste 15 (Saque):
  [Empty - will be skipped]
```

---

## 🔄 WORKFLOW EXAMPLES

### Example 1: Manual Debug of Failing Test
```
1. Frontend shows test 14 failed in previous batch
2. Client wants to debug with different log
3. Uses Manual Mode:
   - Selects Test 14
   - Enters specific DE11/DE42 from log
   - Gets detailed perna-by-perna breakdown
   - Identifies issue (e.g., missing 0430 reversal)
```

### Example 2: Complete Homologation Submission
```
1. Client runs full homologation suite
2. Fills roteiro Word with all test results
3. Uses Batch Mode:
   - Uploads roteiro (auto-extracts tests)
   - Selects production log file
   - Gets summary: "2 approved, 1 failed"
   - Downloads detailed report JSON
   - Fixes issues and resubmits
```

### Example 3: Multi-Day Testing
```
1. Monday: Run tests 1-20, save in roteiro
2. Tuesday: Run tests 21-40, save in roteiro
3. Wednesday: Run tests 41-55, save in roteiro
4. Thursday: 
   - Compile all roteiro sections into one file
   - Upload consolidated roteiro
   - Get results for all 55 tests
   - Submit for approval
```

---

## 📊 RESULT INTERPRETATION

### Status Values
- **SUCESSO:** All tests passed ✅
- **PARCIAL:** Some tests passed, some failed ⚠️
- **FALHA:** All tests failed ❌
- **ERRO:** System error (file not found, etc.) 🔴

### Per-Test Status
- **APROVADO:** Test passed all validations ✅
- **REPROVADO:** Test failed one or more validations ❌
- **ERRO:** Test couldn't be validated (data issue, etc.) 🔴

### Cadeia (Message Chain)
Shows expected message flow (e.g., "0200, 0210, 0420, 0430")
- Indicates complete transaction flow was found
- If empty or incomplete, messages are missing from log

### Percentual_Sucesso
Percentage of tests that passed:
- 100% = All tests approved
- 0% = No tests approved
- 50% = Half passed, half failed

---

## ⚠️ KNOWN LIMITATIONS

### Current Issues
1. **Test ID Format:** Some tests may show as "not found" in CARDSE validator (being debugged)
2. **Log Format:** Requires logs in standard aud_YYYYMMDD.txt format
3. **Batch Size:** No limit enforced, but large batches may take time

### What Won't Work Yet
- ❌ Mixing multiple log files in one batch
- ❌ Custom roteiro formats (only v1.9+ supported)
- ❌ Real-time progress tracking (returns final results only)

---

## 🆘 TROUBLESHOOTING

### Problem: "Nenhum teste com dados completos encontrado"
**Cause:** Roteiro has no rows with all 4 evidence fields filled  
**Solution:** Check that BIT 11 and BIT 42 are not empty for at least one test

### Problem: "Log não encontrado"
**Cause:** Specified log_name doesn't exist  
**Solution:** Use correct log name (e.g., "aud_20260304.txt"), check date

### Problem: "Teste 'XX' não encontrado no roteiro"
**Cause:** Test ID doesn't exist for selected product  
**Solution:** Verify test ID is valid (1-55 for CARDSE), check produto_id

### Problem: All tests return REPROVADO
**Cause:** Likely log file issue or BIT matching problem  
**Solution:** 
1. Try manual mode with same log to debug
2. Verify BIT 11/42 values match log content
3. Check log file encoding (UTF-8 required)

---

## 📞 SUPPORT

For issues or questions:
1. Check BATCH_VALIDATION_SYSTEM.md for technical details
2. Review logs in `data/roteiros/batch_resultados_*.json`
3. Contact support with:
   - Roteiro file (if possible)
   - Log name used
   - Error message received

---

## 🔐 SECURITY NOTES

- Uploaded roteiro files are temporarily stored and deleted after processing
- Result files are saved with timestamps to prevent overwrites
- Manual validation continues working for sensitive single-test debugging
- Both modes log all validation attempts for audit trail

---

## 📅 CHANGE HISTORY

### v1.0 (2026-07-15)
- ✅ Parser: Word roteiro extraction
- ✅ Batch Validator: Multi-test orchestration  
- ✅ API: `/api/validar-roteiro-cliente-batch` endpoint
- ✅ Dual-mode: Manual + Automatic working in parallel
- ⏳ Known: Test ID format issue being debugged

---

## 🎓 APPENDIX: FILE LOCATIONS

```
System Root:
  C:\Users\f1ddaqa\OneDrive - Fiserv Corp\Desktop\Automatizazao Homo\

Parser:
  roteiro_cliente_parser.py

Batch Validator:
  roteiro_batch_validator.py

API Server:
  app_homolog_web.py

Roteiros Folder:
  data/roteiros/
    ├── Roteiro de Homologação FepasCardSE_Cartão (Autorizador)_Versão Cliente 1.9.docx
    ├── roteiro_iso_novo_produto.json (CARDSE test definitions)
    ├── testes_cliente_extraidos.json (sample extraction)
    └── batch_resultados_YYYYMMDD_HHMMSS.json (results)

Logs Folder:
  LOGS de TESTE/
    ├── aud_20260304.txt
    ├── aud_20260305.txt
    └── ...
```

