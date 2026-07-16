# 📋 RESUMO - VALIDAÇÃO AUTORIZADOR CARDSE (TESTE 17)

## 🎯 Objetivo Esperado
**Fluxo:** 0200 → 0210  
**Produto:** Débito (Magnético)  
**Código Esperado:** 002000  

---

## 1️⃣ VALIDAÇÃO 0200 (TERMINAL > FEPAS)

### ✅ O que é validado:
- ✓ **Presença da perna:** Verifica se existe no fluxo esperado
- ✓ **Bit 22 (Entry Mode):** Validação obrigatória
  - Prefixo esperado: `02x` (entrada magnética)
  - Valida capacidade de PIN (3º dígito)
  - **Esta validação SEMPRE ocorre, independente de field validation**

### ❌ O que NÃO é validado (ignore_leg_campos_bits):
- ✗ Campos individuais obrigatórios (BIT 11, 41, 42, etc)
- ✗ Comprimentos de campo
- ✗ Formatos específicos
- ✗ Regras condicionais de bits

### 🔍 Motivo:
```json
"ignore_leg_campos_bits": [
  {
    "mti": "0200",
    "direction": "RECEBIDA"
  }
]
```
**Razão:** TEF envia apenas campos essenciais. Não deve ser negada por omissão de campos.

### 📊 Resultado esperado:
- Status: **APROVADO** ou **Não Aplica** (se não houver erro de BIT 22)
- Erros permitidos: Apenas "Bit 22: prefixo inválido..." (se houver)

---

## 2️⃣ VALIDAÇÃO 0210 (PROC > FEPAS)

### ✅ O que é validado:
- ✓ **Presença da perna:** Verifica se existe no fluxo esperado
- ✓ **Todos os campos obrigatórios:**
  - Bits obrigatórios: 01, 03, 04, 07, 11, 12, 13, 41, 42
  - Comprimentos conforme especificação
  - Formatos de dado (numérico, alfanumérico, binário)
- ✓ **Bit 22 (Entry Mode):** Validação aplicada
- ✓ **Correspondência com 0200:**
  - Bits replicados validam consistência
  - DE42 (Merchant ID) deve ser igual
  - DE41 (Terminal ID) deve ser igual

### 🔍 Por que esta validação é completa:
```json
"required_chain": [
  { "mti": "0200", "de22_prefix": "02" },
  { "mti": "0210" }
]
```
**0210 NÃO está em ignore_leg_campos_bits** → Validação completa!  
**Origem:** Resposta da Processadora (WEBS-RX) → deve ser validada totalmente

### 📊 Resultado esperado:
- Status: **APROVADO** (se todos os campos estiverem corretos)
- Status: **REPROVADO** (se faltar BIT 11, DE22 formato inválido, etc)

---

## 3️⃣ FLUXO DE VALIDAÇÃO DO TESTE 17

```
LOG FEPAS (.fps.txt com 26 pernas)
         ↓
┌─────────────────────────────┐
│ PARSE_ISO_FORMATTED_BLOCKS  │
│ Extrai 26 pernas com:       │
│  • MTI (0200, 0210, etc)    │
│  • Direction (RECEBIDA/ENVIADA)
│  • Bits presentes           │
│  • Headers (WEBS-TX/WEBS-RX)│
└─────────────────────────────┘
         ↓
┌─────────────────────────────┐
│ AVALIAR_TESTE_HOMOLOGACAO  │
│ Filtra pernas relevantes:   │
│  • Teste 17 = [0200, 0210]  │
│  • Outras MTIs descartadas  │
└─────────────────────────────┘
         ↓
     ╔═════════════════════════════════════════╗
     ║  PARA CADA PERNA DO TESTE              ║
     ╚═════════════════════════════════════════╝
         ↓
     ┌──────────────────────────────────────────┐
     │ SE MTI = 0200 (TERMINAL > FEPAS)        │
     ├──────────────────────────────────────────┤
     │ 1. Verificar presença no fluxo esperado  │
     │ 2. PULAR validação de campos             │ ← ignore_leg_campos_bits
     │ 3. Executar BIT 22 validation (sempre!)  │
     │ 4. Status: APROVADO (se BIT22 OK)        │
     └──────────────────────────────────────────┘
         ↓
     ┌────────────────PROC > FEPAS──────────────┐
     │ SE MTI = 0210 (FEPAS > PROC)            │
     ├──────────────────────────────────────────┤
     │ 1. Verificar presença no fluxo esperado  │
     │ 2. Validar TODOS os campos obrigatórios │
     │ 3. Executar BIT 22 validation            │
     │ 4. Validar correspondência com 0200      │
     │ 5. Status: APROVADO (se tudo OK)         │
     │            REPROVADO (se falta algo)     │
     └──────────────────────────────────────────┘
         ↓
┌─────────────────────────────┐
│ RETORNA: pernas_saida[]     │
│  • 17 pernas TERMINAL>FEPAS │
│  •  9 pernas FEPAS>PROC     │
│  • Cada perna com status    │
└─────────────────────────────┘
         ↓
┌─────────────────────────────┐
│ EVIDENCE REPORT             │
│ Exibe:                      │
│  • Total pernas validadas   │
│  • Count aprovadas/reprovadas│
│  • Direction de cada perna  │
│  • Erros detalhados         │
└─────────────────────────────┘
```

---

## 4️⃣ VALIDAÇÃO DO TESTE SELECIONADO (17)

### 📋 Cadeia Obrigatória (required_chain):
```
✓ Perna 1 (TERMINAL > FEPAS):  MTI=0200, DE22=02x (entrada magnética)
✓ Perna 2 (FEPAS > PROC):      MTI=0210
```

### ❌ MTIs Proibidas (forbidden_steps):
```
✗ 0800, 0810, 0100, 0110    (Network Management)
✗ 0202, 0212                 (Crédito/Débito Repetidas)
✗ 0400, 0410, 0402, 0412   (Reversão)
✗ 0420, 0430                (Devolução)
```

### 🎲 Validações Especiais:
```
✓ require_campos_correspondentes: true
  → Bits replicados entre 0200 e 0210 devem ser iguais
  
✓ Bit 22 Entry Mode: Enabled
  → Prefixo válido: 02 (magnético)
  → PIN capability: validado no 3º dígito
```

### 📊 Contadores Esperados:
```
Total pernas no teste: 2
 ├─ TERMINAL > FEPAS (0200): 1 perna
 └─ FEPAS > PROC (0210):     1 perna
```

---

## 5️⃣ ESTRUTURA DE VALIDAÇÃO

| Aspecto | 0200 (TERMINAL>FEPAS) | 0210 (FEPAS>PROC) |
|---------|----------------------|------------------|
| Aspecto | 0200 (TERMINAL>FEPAS) | 0210 (PROC>FEPAS) |
|---------|----------------------|------------------|
| **Presença** | ✓ Obrigatória | ✓ Obrigatória |
| **Campos** | ✗ Ignorados | ✓ Todos validados |
| **Bit 22** | ✓ Validado | ✓ Validado |
| **Correspondência** | N/A | ✓ Com 0200 |
| **Status Success** | Sem erros de BIT22 | Sem erros totais |
| **Config** | `{"mti":"0200","direction":"RECEBIDA"}` | Sem ignore |
| **Origem** | WEBS-TX (Terminal) | WEBS-RX (Processadora) |

---

## 🔑 Valores de Teste 17

```
Data Teste: 2026-05-25
Arquivo: 20260713_120211_17_evidencia.txt

Campos Validados (0210):
├─ BIT 11: RRN (Número Único de Referência)
├─ BIT 22: Entry Mode = "02" + PIN capability
├─ DE42: Merchant ID = 056237933000151
├─ DE41: Terminal ID = variável
├─ Bits obrigatórios: 01, 03, 04, 07, 11, 12, 13, 41, 42
└─ Correspondência: DE42 e DE41 iguais entre 0200 e 0210

BIT 22 Entry Mode (0200 e 0210):
├─ Prefixo: 02 (entrada magnética) ✓
├─ Código: 02x (onde x = capacidade de PIN)
└─ Regra: De22_prefix="02" obrigatório para teste 17
```

---

## ⚙️ Código Configuração (roteiro_iso_novo_produto.json - Teste 17)

```json
{
  "id": "17",
  "nome": "Realizar o teste de Compra Débito (magnético)",
  "objetivo_esperado": "0200 - 0210",
  
  "rule": {
    "require_campos_correspondentes": true,
    
    "ignore_leg_campos_bits": [
      {
        "mti": "0200",
        "direction": "RECEBIDA"  ← CHAVE: Não valida 0200
      }
    ],
    
    "required_chain": [
      { "mti": "0200", "de22_prefix": "02" },
      { "mti": "0210" }
    ],
    
    "forbidden_steps": [
      { "any_mti": ["0800","0810","0100","0110","0202",...] }
    ]
  },
  
  "product_type": "debito",
  "expected_pcode": "002000"
}
```

---

## ✅ RESUMO EXECUTIVO

**Teste 17: Débito Magnético**

```
┌─────────────────────────────────────────────────┐
│ 0200 (TERMINAL > FEPAS)                         │
├─────────────────────────────────────────────────┤
│ • Valida apenas BIT 22 (Entry Mode = "02")      │
│ • Não reprova por falta de campos (ignorados)   │
│ • Status: APROVADO (se BIT22 OK)                │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│ 0210 (PROC > FEPAS)                             │
├─────────────────────────────────────────────────┤
│ • Valida TODOS os campos obrigatórios          │
│ • Valida correspondência com 0200 (DE42, DE41) │
│ • Valida BIT 22                                 │
│ • Status: APROVADO (se tudo OK) ou             │
│           REPROVADO (se falta algo)             │
└─────────────────────────────────────────────────┘
```

**Resultado Esperado:**
- ✅ 0200: APROVADO (somente BIT 22 validado)
- ✅ 0210: APROVADO (campos completos)
- ✅ Teste 17: APROVADO (fluxo completo)

