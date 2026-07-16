# API Multi-Produto - Documentação

## Visão Geral
A API de homologação agora suporta múltiplos produtos, cada um com suas próprias regras de validação.

## Produtos Disponíveis

### Produto 01: Homologação QR Pago
- **ID**: `01`
- **Nome**: Homologação QR Pago
- **Tipo de Validação**: Bidirecionais (FEPAS ↔ PROCESSADORA)
- **Roteiro**: `roteiro_iso_0200.json`
- **Validador**: `validador_0200.py`
- **Descrição**: Validador para transações QR Pago com fluxos completos

### Produto 02: Homologação Autorizador  
- **ID**: `02`
- **Nome**: Homologação Autorizador
- **Tipo de Validação**: Apenas Processadora (PROCESSADORA → FEPAS)
- **Roteiro**: `roteiro_iso_novo_produto.json` (Autorizador CARDSE)
- **Validador**: `validador_cardse.py`
- **Descrição**: Validador para Autorizador CARDSE - apenas mensagens recebidas da processadora

## Endpoints da API

### 1. Listar Produtos Disponíveis
```
GET /api/produtos
```

**Resposta Sucesso (200)**:
```json
{
  "produtos": [
    {
      "id": "01",
      "nome": "Homologação QR Pago",
      "descricao": "Validador para transações QR Pago com fluxos completos",
      "tipo_validacao": "bidirecionais"
    },
    {
      "id": "02",
      "nome": "Homologação Autorizador",
      "descricao": "Validador para Autorizador CARDSE - apenas mensagens recebidas da processadora",
      "tipo_validacao": "processadora_apenas"
    }
  ]
}
```

---

### 2. Obter Testes de um Produto
```
GET /api/produtos/{produto_id}/tests
```

**Parâmetros**:
- `produto_id` (path): ID do produto (01 ou 02)

**Resposta Sucesso (200)**:
```json
{
  "tests": [
    {
      "id": "01",
      "nome": "Logon",
      "descricao": "Fluxo de logon e resposta de logon.",
      "objetivo_esperado": "0800 - 0810"
    },
    {
      "id": "02",
      "nome": "Consulta",
      "descricao": "Fluxo de consulta e resposta da consulta.",
      "objetivo_esperado": "0100 - 0110"
    }
  ]
}
```

---

### 3. Validar Log com Produto
```
POST /api/validate-produto
```

**Parâmetros (form)**:
- `produto_id` (opcional, padrão: "01"): ID do produto (01 ou 02)
- `teste_id` (obrigatório): ID do teste a validar
- `log_name` (obrigatório): Nome do arquivo de log  
- `de11` (opcional): Bit 11 para filtro
- `de41` (opcional): Bit 41 para filtro

**Exemplo de Requisição**:
```bash
curl -X POST http://localhost:5000/api/validate-produto \
  -F "produto_id=02" \
  -F "teste_id=01" \
  -F "log_name=aud_20260310_autorizador.txt"
```

**Resposta Sucesso (200)**:
```json
{
  "status": "APROVADO",
  "teste_id": "01",
  "resumo": "30/30 mensagens validadas com sucesso",
  "total_pernas": 30,
  "blocos_processados": 30,
  "api_metadata": {
    "log_name": "aud_20260310_autorizador.txt",
    "log_size_bytes": 123456,
    "produto_id": "02",
    "produto_nome": "Homologação Autorizador",
    "tipo_validacao": "processadora_apenas",
    "cached": false
  }
}
```

---

### 4. Validar Cliente com Produto
```
POST /api/client/validate-produto
```

**Parâmetros (form)**:
- `produto_id` (opcional, padrão: "01"): ID do produto
- `cnpj` (obrigatório): CNPJ do cliente
- `data_teste` (obrigatório): Data do teste (YYYY-MM-DD ou DD/MM/YYYY)
- `teste_id` (obrigatório): ID do teste
- `de11` (obrigatório): Bit 11
- `de41` (obrigatório): Bit 41

**Exemplo de Requisição**:
```bash
curl -X POST http://localhost:5000/api/client/validate-produto \
  -F "produto_id=02" \
  -F "cnpj=12345678000190" \
  -F "data_teste=2026-05-13" \
  -F "teste_id=01" \
  -F "de11=123456" \
  -F "de41=12345678"
```

---

## Mudanças Importantes

### Para Produto 02 (Autorizador)
- **Validação Filtra**: Apenas mensagens com marcador `(PROCESSADORA -> FEPAS)` são validadas
- **Bits Obrigatórios**: Reduzido para mensagens de resposta (não exigem todos os bits)
- **Roteiro Dedicado**: Usa `roteiro_iso_novo_produto.json` com 5 testes específicos
- **Validador Específico**: `validador_cardse.py` com lógica otimizada para autorização

### Compatibilidade com API Existente
- Endpoints antigos (`/api/validate`, `/api/client/validate`) continuam funcionando
- Padrão para produto é `01` (QR Pago)
- Novos endpoints usam sufixo `-produto` para clareza

---

## Exemplos de Uso

### Fluxo Completo para Autorizador CARDSE

1. **Listar produtos**:
```bash
curl http://localhost:5000/api/produtos
```

2. **Obter testes do Autorizador**:
```bash
curl http://localhost:5000/api/produtos/02/tests
```

3. **Validar log do Autorizador**:
```bash
curl -X POST http://localhost:5000/api/validate-produto \
  -F "produto_id=02" \
  -F "teste_id=01" \
  -F "log_name=aud_20260310_autorizador.txt"
```

---

## Estrutura de Resposta de Validação

### Status Possíveis
- `APROVADO`: Todas as mensagens/pernas foram validadas com sucesso
- `REPROVADO`: Uma ou mais mensagens/pernas falharam na validação
- `FALHA`: Erro ao processar a validação

### Campos de Resposta
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | string | Status da validação |
| `teste_id` | string | ID do teste validado |
| `resumo` | string | Resumo da validação |
| `total_pernas` | int | Total de mensagens/pernas processadas |
| `blocos_processados` | int | Quantidade de blocos validados |
| `erros` | array | Lista de erros encontrados |
| `api_metadata` | object | Metadados da execução |

---

## Configuração de Produtos

Para adicionar novos produtos, edite `products_config.py`:

```python
PRODUTOS = {
    "03": {
        "id": "03",
        "nome": "Novo Produto",
        "descricao": "Descrição do novo produto",
        "roteiro_path": "roteiro_novo.json",
        "validador_module": "validador_novo",
        "validador_function": "validar_novo",
        "tipo_validacao": "tipo_validacao",
    },
    # ... outros produtos
}
```

A função de validação deve ter a assinatura:
```python
def validar_novo(
    log_text: str,
    teste_id: str = "",
    de11: str = "",
    de41: str = "",
    cliente: str = "LOCAL",
    debug: bool = False,
) -> Dict[str, Any]:
    # Retorna dicionário com campos padrão
    return {
        "status": "APROVADO" | "REPROVADO" | "FALHA",
        "resumo": "...",
        "teste_id": "...",
        "total_pernas": int,
        "blocos_processados": int,
        "erros": [],
        # ... outros campos opcionais
    }
```
