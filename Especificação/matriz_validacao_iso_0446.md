# Matriz de Validacao ISO 8583 - CardSE v04.46

## Fonte
- Documento: CardSE_Especificacao_ISO8583_FEPAS_Autorizador_versao_04.46_PT.pdf
- Extracao textual: CardSE_Especificacao_ISO8583_FEPAS_Autorizador_versao_04.46_PT.txt

## Regras principais confirmadas

### 1) DE22 (Point of Service Entry Mode)
- Conteudo do DE22: n3.
- Primeiros 2 digitos (modo de entrada):
  - 00: nao especificado
  - 01: digitado manual
  - 02: tarja magnetica
  - 05: chip EMV
  - 07: contactless chip
  - 50: carteira digital
  - 79: fallback digitado do chip
  - 80: fallback magnetico do chip
  - 91: contactless tarja magnetica
- Terceiro digito (capacidade de PIN):
  - 0: nao especificado
  - 1: com PIN
  - 2: sem PIN

### 2) Compra Credito/Debito (0200/0210/0202/0212)
- No quadro de Compra Credito/Debito:
  - DE22 em 0200: M (obrigatorio).
  - DE35 em 0200: referencia 40.
  - DE45 em 0200: referencia 02.
- Tabela de condicoes:
  - Regra 02: DE45/DE35 presente se leitura de tarja magnetica; usar ambos quando ambas trilhas forem lidas.
  - Regra 40: presente se leitura de tarja magnetica ou chip EMV; usar DE35 e DE45 quando ambas trilhas forem lidas.

### 3) Cancelamento (0400/0410/0402/0412)
- No quadro de Cancelamento:
  - DE22 em 0400: referencia 68.
- Tabela de condicoes:
  - Regra 68: obrigatorio para todos os casos, exceto Compra Servico (pcode 964000).

### 4) Semantica de obrigatoriedade nas tabelas
- M: obrigatorio.
- O: opcional (pode virar obrigatorio por condicao).
- ME: obrigatorio com eco.
- OE: opcional com eco.

## Impacto pratico para homologacao

### Teste de Compra Debito (magnetico)
Para um teste de compra debito magnetico, a validacao minima recomendada e:
- Fluxo: 0200 -> 0210 (e, quando aplicavel, 0202 -> 0212).
- DE22 no 0200:
  - Estritamente magnetico puro: prefixo 02.
  - Se desejar aceitar cenarios correlatos, incluir 80 (fallback magnetico) e 91 (contactless tarja magnetica).
- Campos de trilha:
  - Exigir DE35 e/ou DE45 conforme regra operacional de leitura.
  - Quando ambas trilhas existirem, exigir ambos.

## Lacuna atual do validador
- O motor de regras atual trabalha bem com MTI, DE03, DE39 e IDs de DE47 em passos.
- Ainda nao ha operador nativo no passo para validar DE22 diretamente (exemplo: de22_prefix).
- Para cobrir "magnetico" com precisao automatica, sera necessario adicionar validacao de DE22 no motor de regras.

## Proxima entrega planejada
1. Adicionar suporte a DE22 no motor de passos do validador.
2. Ajustar o teste 22 para compra debito magnetico com cadeia e condicoes especificas.
3. Definir se DE22 aceito no teste 22 sera apenas 02 ou tambem 80/91.
# Matriz de Validacao ISO 8583 - CardSE 04.46

Fonte analisada: CardSE_Especificacao_ISO8583_FEPAS_Autorizador_versao_04.46_PT.pdf
Texto extraido: CardSE_Especificacao_ISO8583_FEPAS_Autorizador_versao_04.46_PT.txt

## Criterio de obrigatoriedade

- M: dado obrigatorio.
- O: dado opcional (pode virar obrigatorio por condicao).
- ME: obrigatorio com eco do conteudo da mensagem anterior.
- OE: opcional com eco.
- <nn>: obrigatoriedade condicional dada pela Tabela de Condicoes (item 8.2.6).

## DE22 - Modo de entrada do cartao

Os dois primeiros digitos do DE22 identificam o modo de entrada:

- 00: nao especificado
- 01: digitado
- 02: tarja magnetica
- 05: chip EMV
- 07: contactless chip
- 50: carteira digital
- 79: fallback digitado do chip
- 80: fallback magnetico do chip
- 91: contactless tarja magnetica

O terceiro digito do DE22 indica capacidade de PIN:

- 0: nao especificado
- 1: terminal com capacidade de PIN
- 2: terminal sem capacidade de PIN

## Compra Credito/Debito (8.2.4.1)

Tabela principal 0200/0210/0202/0212:

- DE22: M no 0200
- DE35: referencia 40
- DE45: referencia 02

Condicoes relevantes (8.2.6):

- 02: trilha magnetica presente (bits 35 e/ou 45)
- 40: presente em operacao com leitura de tarja magnetica ou chip EMV

Leitura pratica para validacao:

- Compra com entrada magnetica deve ter DE22 com prefixo 02.
- Para magnetica, DE35 ou DE45 devem estar presentes (idealmente ambos quando as duas trilhas foram lidas).
- O DE22 deve manter o terceiro digito coerente com a capacidade de PIN do terminal.

## Cancelamento (8.2.4.9)

- DE22 em 0400 aparece com condicao 68.
- Condicao 68: obrigatorio para todos os casos, exceto compra servico (pcode 964000).

## Regras candidatas para automatizar no validador

1. Permitir validacao de DE22 por passo do fluxo (required_chain e forbidden_steps), incluindo:
- de22
- de22_prefix
- any_de22_prefix

2. Incluir validacoes por categoria de entrada:
- magnetica: DE22 prefixo 02 (e opcionalmente 80 e 91, se definido como magnetico expandido)
- chip: DE22 prefixo 05
- contactless chip: DE22 prefixo 07
- digitado: DE22 prefixo 01 ou 79

3. Para compra debito magnetica (exemplo teste 22):
- required_chain deve exigir 0200 e 0210
- perna 0200 deve validar de22_prefix = 02
- perna 0200 deve validar presenca de DE35 ou DE45

## Duvidas para fechar regra de negocio

- Fallback magnetico (80) deve ser aceito como entrada magnetica no mesmo teste da tarja pura (02), ou deve ser teste separado?
- Contactless tarja (91) entra como magnetica para homologacao, ou como cenario proprio?
