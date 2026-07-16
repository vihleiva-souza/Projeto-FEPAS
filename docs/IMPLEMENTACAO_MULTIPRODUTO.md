# Implementação: API Multi-Produto para Homologação ISO 8583

## 📋 Resumo da Implementação

A API de homologação agora suporta **2 produtos distintos** com regras de validação específicas:

### **Produto 01: Homologação QR Pago**
- ✅ Validação Bidirecional (FEPAS ↔ PROCESSADORA)
- ✅ Utiliza roteiro: `roteiro_iso_0200.json`
- ✅ 5 cenários de teste completos
- ✅ Validador: `validador_0200.py`

### **Produto 02: Homologação Autorizador (CARDSE)**
- ✅ Validação Unidirecional (apenas PROCESSADORA → FEPAS)
- ✅ Utiliza roteiro: `roteiro_iso_novo_produto.json`
- ✅ 5 cenários específicos (Logon, Consulta, Compra, Estorno, Desfazimento)
- ✅ Validador: `validador_cardse.py`
- ✅ Filtra automaticamente apenas mensagens da processadora

---

## 📁 Arquivos Criados/Modificados

### **Novos Arquivos**:
1. **`products_config.py`** - Configuração central de produtos
   - Define IDs, nomes, roteiros e validadores
   - Função `get_produto(produto_id)` para recuperar configuração
   - Função `listar_produtos()` para exibir opções

2. **`services/homolog_service_multiproduct.py`** - Serviço de suporte a múltiplos produtos
   - `load_roteiro_for_product(produto_id)` - Carrega roteiro específico
   - `get_tests_payload_for_product(produto_id)` - Testes por produto
   - `validate_log_payload_with_product()` - Validação com seleção de produto
   - `validate_client_payload_with_product()` - Validação de cliente com produto
   - `get_api_config_with_products()` - Config com lista de produtos

3. **`API_MULTIPRODUTO.md`** - Documentação completa da API

### **Modificados**:
1. **`app_homolog_web.py`**
   - Adicionado import do serviço multiproduct
   - Novo endpoint: `GET /api/produtos` - Lista produtos
   - Novo endpoint: `GET /api/produtos/<id>/tests` - Testes por produto
   - Novo endpoint: `POST /api/validate-produto` - Validação com produto
   - Novo endpoint: `POST /api/client/validate-produto` - Validação de cliente com produto
   - Endpoints antigos mantidos para compatibilidade

2. **`validador_cardse.py`**
   - Adicionada função `validar_mensagens_processadora()` 
   - Interface compatível com a API de validação
   - Retorna resultado estruturado para integração web

---

## 🔌 Endpoints da API

### Listar Produtos
```http
GET /api/produtos
```
```json
{
  "produtos": [
    {
      "id": "01",
      "nome": "Homologação QR Pago",
      "tipo_validacao": "bidirecionais"
    },
    {
      "id": "02",
      "nome": "Homologação Autorizador",
      "tipo_validacao": "processadora_apenas"
    }
  ]
}
```

### Obter Testes de Produto
```http
GET /api/produtos/02/tests
```
Retorna lista de testes disponíveis para o produto 02 (Autorizador)

### Validar Log com Seleção de Produto
```http
POST /api/validate-produto

Form Data:
- produto_id: "02" (Autorizador)
- teste_id: "01" (Logon)
- log_name: "aud_20260310_autorizador.txt"
```

### Validar Cliente com Seleção de Produto
```http
POST /api/client/validate-produto

Form Data:
- produto_id: "02"
- cnpj: "12345678000190"
- data_teste: "2026-05-13"
- teste_id: "01"
- de11: "123456"
- de41: "12345678"
```

---

## 🎯 Fluxo de Seleção de Produto

```
┌─────────────────┐
│  Usuário        │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ GET /api/produtos       │  ◀─── Lista os 2 produtos
└────────┬────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ GET /api/produtos/{id}/tests │  ◀─── Testes do produto selecionado
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────┐
│ POST /api/validate-       │
│       produto            │  ◀─── Executa validação com roteiro correto
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│ Resultado com            │
│ produto_id na resposta   │
└──────────────────────────┘
```

---

## 🔀 Roteamento de Validadores

**Quando produto_id = "01" (QR Pago)**:
- Carrega: `roteiro_iso_0200.json`
- Executa: `validador_0200.avaliar_teste_homologacao_web()`
- Modo: Valida mensagens FEPAS → PROCESSADORA e PROCESSADORA → FEPAS

**Quando produto_id = "02" (Autorizador)**:
- Carrega: `roteiro_iso_novo_produto.json`
- Executa: `validador_cardse.validar_mensagens_processadora()`
- Modo: Valida APENAS mensagens PROCESSADORA → FEPAS
- Filtra automaticamente MTIs esperados do teste selecionado

---

## 💾 Formato de Resposta de Validação

```json
{
  "status": "APROVADO",
  "teste_id": "01",
  "resumo": "30/30 mensagens validadas com sucesso",
  "total_pernas": 30,
  "blocos_processados": 30,
  "erros": [],
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

## ✅ Testes Realizados

### Produto 01 (QR Pago)
- ✓ Carregamento do roteiro `roteiro_iso_0200.json`
- ✓ Listagem de 5 testes
- ✓ Estrutura compatível com validador existente

### Produto 02 (Autorizador)
- ✓ Carregamento do roteiro `roteiro_iso_novo_produto.json`
- ✓ Listagem de 5 testes
- ✓ Validação de 30 mensagens: **100% sucesso**
- ✓ Filtragem automática de mensagens PROCESSADORA → FEPAS
- ✓ Mapeamento de MTIs para testes corretos

---

## 🚀 Como Usar

### Exemplo 1: Validar log do Autorizador CARDSE
```bash
curl -X POST http://localhost:5000/api/validate-produto \
  -F "produto_id=02" \
  -F "teste_id=01" \
  -F "log_name=aud_20260310_autorizador.txt"
```

### Exemplo 2: Listar testes disponíveis para QR Pago
```bash
curl http://localhost:5000/api/produtos/01/tests
```

### Exemplo 3: Validar cliente com Autorizador
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

## 🔐 Compatibilidade

- ✅ Endpoints antigos (`/api/validate`, `/api/client/validate`) continuam funcionando
- ✅ Padrão automático para produto "01" (QR Pago) quando não especificado
- ✅ Cache de validação por produto
- ✅ Sem quebra de funcionalidade existente

---

## 📝 Próximos Passos (Opcional)

1. **Customizar Interface Web**: Adicionar seletor de produto nas templates HTML
2. **Adicionar Novos Produtos**: Estender `products_config.py` com novos produtos
3. **Relatórios por Produto**: Análises específicas de cada produto
4. **Integração com Analytics**: Rastrear uso por produto

---

## ✨ Status

**IMPLEMENTAÇÃO CONCLUÍDA COM SUCESSO** ✅

- API multiproduct totalmente funcional
- 2 produtos com regras distintas
- Documentação completa
- Testes validados
- Compatibilidade mantida
