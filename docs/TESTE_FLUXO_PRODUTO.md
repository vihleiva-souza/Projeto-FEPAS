# Testes - Fluxo de Seleção de Produto

## Cenário 1: Acessar como QR Pago
1. Entrar em `/cliente`
2. Deve ver tela de **Selecione o tipo de produto** com 2 cards
3. Clicar em **QR Pago**
4. Deve aparecer formulário com campo **CNPJ/CUIT**
5. Digitar CNPJ/CUIT e clicar em "Acessar homologações"
6. Sistema carrega testes do QR Pago (20 testes)
7. Seleciona um teste QR e envia validação
8. Valida com validador_0200 (produto 01)

## Cenário 2: Acessar como Autorizador
1. Entrar em `/cliente`
2. Ver tela de **Selecione o tipo de produto** com 2 cards
3. Clicar em **Autorizador CARDSE**
4. Deve aparecer formulário com campo **CNPJ** apenas (sem CUIT)
5. Digitar CNPJ e clicar em "Acessar homologações"
6. Sistema carrega testes do Autorizador (5 testes)
7. Seleciona um teste Autorizador e envia validação
8. Valida com validador_cardse (produto 02, apenas PROCESSADORA->FEPAS)

## Cenário 3: Voltar para Seleção
1. Em qualquer ponto, clicar em "← Voltar para seleção"
2. Volta à tela inicial de seleção de produto
3. Pode escolher outro produto

## Cenário 4: Trocar Produto
1. Acessou com QR Pago
2. Depois clica em "Trocar CNPJ/CUIT"
3. Volta à seleção de produto
4. Pode escolher Autorizador agora

## Mudanças de Código Implementadas

### Frontend
- ✅ Adicionado `/static/product-selection.js` com lógica de seleção
- ✅ Adicionado seção de seleção de produto em `client.html`
- ✅ Formulário de acesso agora tem campos condicionais
- ✅ Script `product-selection.js` carregado antes de `client.js`

### JavaScript - client.js
- ✅ Modificado `getCnpjFromForm()` para usar input correto
- ✅ Modificado `loadTests(productId)` para carregar testes do produto
- ✅ Modificado `loadClientProgress()` para passar produto_id na URL
- ✅ Form submit modificado para usar `/api/client/validate-produto` com produto_id
- ✅ Inicialização modificada para carregar testes e progresso do produto salvo

### API - Endpoints Requeridos
- ✅ `/api/produtos` - Retorna lista de produtos (já existe)
- ✅ `/api/produtos/{id}/tests` - Retorna testes do produto (já existe)
- ✅ `/api/client/progress?cnpj=X&produto_id=X` - Carrega progresso com produto (NOVO - precisa ajuste)
- ✅ `/api/client/validate-produto` - Valida com produto selecionado (NOVO - já existe)

## Status: PRONTO PARA TESTE
