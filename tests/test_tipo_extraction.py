"""
Script para testar se as funções de extração de tipo estão funcionando com ambas as formas de chave
"""
from validador_0200 import (
    _extrair_texto_bit62_apos_segundo_arroba,
    _extrair_texto_bit48_apos_segundo_arroba,
    _extrair_id505_bit62,
    _extrair_id506_bit48,
    _tipo_por_texto_bit48
)

# Criar uma perna fake com Bit 62 contendo "VISA CREDITO" após segundo @
# Testar com ambas as formas de chave

print("=== Teste 1: Bit 62 como chave STRING ===")
perna1 = {
    "mti": "0210",
    "bits": {
        "62": "DADOS1@DADOS2@VISA CREDITO"  # Chave string
    }
}

resultado1 = _extrair_texto_bit62_apos_segundo_arroba(perna1)
print(f"Resultado: {repr(resultado1)}")
print(f"Sucesso: {resultado1 == 'VISA CREDITO'}")

print("\n=== Teste 2: Bit 62 como chave INT ===")
perna2 = {
    "mti": "0210",
    "bits": {
        62: "DADOS1@DADOS2@VISA CREDITO"  # Chave int
    }
}

resultado2 = _extrair_texto_bit62_apos_segundo_arroba(perna2)
print(f"Resultado: {repr(resultado2)}")
print(f"Sucesso: {resultado2 == 'VISA CREDITO'}")

print("\n=== Teste 3: Tipo por texto ===")
tipo = _tipo_por_texto_bit48("VISA CREDITO")
print(f"Tipo detectado de 'VISA CREDITO': {tipo}")
print(f"Sucesso (deve ser 'credito'): {tipo == 'credito'}")

print("\n=== Teste 4: Bit 48 como chave INT ===")
perna3 = {
    "mti": "0210",
    "bits": {
        48: "DADOS1@DADOS2@CREDITO EM 01"  # Chave int
    }
}

resultado3 = _extrair_texto_bit48_apos_segundo_arroba(perna3)
print(f"Resultado: {repr(resultado3)}")
print(f"Sucesso: {resultado3 == 'CREDITO EM 01'}")

tipo2 = _tipo_por_texto_bit48(resultado3)
print(f"Tipo detectado: {tipo2}")

print("\n=== Resumo ===")
print("Se todos os testes passaram com 'Sucesso: True', o problema foi corrigido!")
