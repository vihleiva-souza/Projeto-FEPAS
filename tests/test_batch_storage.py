#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de teste para validar o salvamento de arquivos na pasta do cliente.
Verifica se os 3 arquivos são criados corretamente:
  - roteiro_original.docx
  - resultado_validacao.json
  - resumo.txt
"""

import json
import os
import sys
from pathlib import Path

# Fix para encoding em Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from roteiro_cliente_parser import parsear_roteiro_docx
from roteiro_batch_validator import validar_roteiro_batch, _salvar_resultados_interno

def test_batch_storage():
    """Testa o fluxo completo de validação e salvamento."""
    
    # Configurações de teste
    roteiro_file = "data/roteiros/Roteiro de Homologação FepasCardSE_Cartão (Autorizador) _Versão Cliente 1.9.docx"
    roteiro_temp = "data/roteiros/roteiro_temp.docx"
    
    # Se a cópia temporária existe, usar ela (arquivo original pode estar bloqueado)
    if Path(roteiro_temp).exists():
        roteiro_file = roteiro_temp
    
    log_file = r"LOGS de TESTE\aud_20260304.txt"  # ✅ LOG CORRETO DE 04/03
    cnpj_teste = "00047118230855"
    
    print("\n" + "=" * 80)
    print("TESTE DE ARMAZENAMENTO EM BATCH")
    print("=" * 80)
    
    # Verificar arquivos de entrada
    if not Path(roteiro_file).exists():
        print(f"❌ Arquivo roteiro não encontrado: {roteiro_file}")
        return False
    
    if not Path(log_file).exists():
        print(f"❌ Arquivo log não encontrado: {log_file}")
        return False
    
    print(f"\n✅ Arquivos de entrada encontrados")
    print(f"   Roteiro: {roteiro_file}")
    print(f"   Log: {log_file}")
    
    # Etapa 1: Extrair testes
    print(f"\n1️⃣  Extraindo testes do roteiro...")
    try:
        testes = parsear_roteiro_docx(roteiro_file)
        print(f"   ✅ {len(testes)} testes extraídos")
        
        # Listar alguns testes
        for teste in testes[:3]:
            print(f"      - Teste {teste['teste_id']}: BIT11={teste['bit11'][:8]}..., BIT42={teste['bit42'][:8]}...")
        if len(testes) > 3:
            print(f"      ... e mais {len(testes) - 3} testes")
    except Exception as e:
        print(f"   ❌ Erro ao extrair: {e}")
        return False
    
    # Etapa 2: Validar em batch COM salvamento
    print(f"\n2️⃣  Validando em batch (com salvamento automático)...")
    try:
        resultado = validar_roteiro_batch(
            log_name=Path(log_file).name,
            testes=testes,
            cnpj=cnpj_teste,
            testes_selecionados=[3, 14, 15],  # ✅ TODOS OS TESTES DO ROTEIRO
            produto_id="02",
            cliente=cnpj_teste,
            roteiro_path=roteiro_file,  # IMPORTANTE: passar o roteiro
            debug=True,
        )
        print(f"\n   ✅ Validação concluída")
        print(f"      Status: {resultado['status']}")
        print(f"      Resumo: {resultado['resumo']}")
    except Exception as e:
        print(f"   ❌ Erro na validação: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Etapa 3: Verificar arquivos salvos
    print(f"\n3️⃣  Verificando arquivos salvos...")
    
    # Construir caminho esperado
    timestamp = resultado['timestamp'].replace('T', '').replace(':', '').split('.')[0][:8] + '_' + resultado['timestamp'].replace('T', '').replace(':', '').split('.')[0][8:14]
    pasta_esperada = Path(f"data/clientes/{cnpj_teste}/submissoes/{timestamp}")
    
    # Tentar encontrar a pasta criada
    pasta_cliente = Path(f"data/clientes/{cnpj_teste}/submissoes")
    if not pasta_cliente.exists():
        print(f"   ❌ Pasta do cliente não foi criada: {pasta_cliente}")
        return False
    
    # Listar submissões criadas
    submissoes = list(pasta_cliente.glob("*"))
    if not submissoes:
        print(f"   ❌ Nenhuma submissão encontrada em {pasta_cliente}")
        return False
    
    # Usar a mais recente
    submissao_recente = max(submissoes, key=os.path.getmtime)
    
    print(f"   ✅ Pasta criada: {submissao_recente}")
    
    # Verificar os 3 arquivos obrigatórios
    arquivos_esperados = [
        ("roteiro_original.docx", "Arquivo roteiro original"),
        ("resultado_validacao.json", "Resultado em JSON"),
        ("resumo.txt", "Resumo em texto"),
    ]
    
    todos_ok = True
    for nome_arquivo, descricao in arquivos_esperados:
        caminho = submissao_recente / nome_arquivo
        if caminho.exists():
            tamanho = caminho.stat().st_size
            print(f"   ✅ {nome_arquivo:25} ({tamanho:8} bytes) - {descricao}")
            
            # Validação específica por tipo
            if nome_arquivo == "resultado_validacao.json":
                try:
                    with open(caminho, 'r', encoding='utf-8') as f:
                        dados = json.load(f)
                    print(f"      └─ Contém: {len(dados.get('resultados', []))} resultados de teste")
                except Exception as e:
                    print(f"      └─ ⚠️  Erro ao ler JSON: {e}")
            
            elif nome_arquivo == "resumo.txt":
                try:
                    with open(caminho, 'r', encoding='utf-8') as f:
                        conteudo = f.read()
                    num_linhas = len(conteudo.split('\n'))
                    print(f"      └─ Contém: {num_linhas} linhas de texto")
                except Exception as e:
                    print(f"      └─ ⚠️  Erro ao ler TXT: {e}")
        else:
            print(f"   ❌ {nome_arquivo:25} - NÃO ENCONTRADO")
            todos_ok = False
    
    print("\n" + "=" * 80)
    if todos_ok:
        print("✅ TESTE PASSOU! Todos os arquivos foram salvos corretamente.")
        print(f"   Pasta de auditoria: {submissao_recente}")
    else:
        print("❌ TESTE FALHOU! Nem todos os arquivos foram salvos.")
    
    print("=" * 80 + "\n")
    
    return todos_ok


if __name__ == "__main__":
    sucesso = test_batch_storage()
    exit(0 if sucesso else 1)
