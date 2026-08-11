"""
Batch validator para testes extraídos do roteiro do cliente.
Permite validação em lote de múltiplos testes contra um log.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from roteiro_cliente_parser import parsear_roteiro_docx
from homolog_service import validate_log_payload
from services.homolog_service_multiproduct import validate_log_payload_with_product


def _is_autorizador_product(produto_id: str) -> bool:
    pid = str(produto_id or "").strip().upper()
    return pid in {"02", "2", "02_AUTORIZADORCARDSE"}


def _date_from_log_name(log_name: str) -> str:
    """Extrai YYYYMMDD do nome do log (ex: aud_20260803.txt → '20260803')."""
    m = re.search(r'(\d{8})', str(log_name or ""))
    return m.group(1) if m else ""


def _date_from_test(data_hora: str) -> str:
    """Converte datas do roteiro para YYYYMMDD com separadores flexíveis."""
    raw = str(data_hora or "")

    # DD/MM/YY, DD-MM-YY, DD.MM.YY
    m0 = re.search(r'(\d{2})[\/\-.](\d{2})[\/\-.](\d{2})', raw)
    if m0:
        yy = int(m0.group(3))
        yyyy = 2000 + yy if yy <= 69 else 1900 + yy
        return f"{yyyy:04d}{m0.group(2)}{m0.group(1)}"

    # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    m = re.search(r'(\d{2})[\/\-.](\d{2})[\/\-.](\d{4})', raw)
    if m:
        return f"{m.group(3)}{m.group(2)}{m.group(1)}"

    # YYYY/MM/DD, YYYY-MM-DD, YYYY.MM.DD
    m2 = re.search(r'(\d{4})[\/\-.](\d{2})[\/\-.](\d{2})', raw)
    if m2:
        return f"{m2.group(1)}{m2.group(2)}{m2.group(3)}"

    # Fallback compacto: YYYYMMDD
    m3 = re.search(r'\b(\d{8})\b', raw)
    if m3:
        return m3.group(1)

    return ""


def validar_roteiro_batch(
    log_name: str,
    testes: List[Dict[str, Any]],
    cnpj: str = "LOCAL",
    testes_selecionados: Optional[List[int]] = None,
    produto_id: str = "02",
    cliente: str = "LOCAL",
    roteiro_path: Optional[str] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Valida um lote de testes contra um log, respeitando seleção de testes.
    
    Args:
        log_name: Nome do arquivo de log
        testes: Lista de testes extraídos do roteiro (pode ter mais que os selecionados)
        cnpj: CNPJ do cliente (para organizar pasta de resultados)
        testes_selecionados: Lista de IDs de testes permitidos para validar (ex: [1, 2, 4])
                            Se None, valida todos os testes extraídos
        produto_id: ID do produto (default "02" para CARDSE)
        cliente: Identificador do cliente
        roteiro_path: Caminho do arquivo roteiro original (será copiado para pasta de auditoria)
        debug: Modo debug
    
    Comportamento:
    - Se cliente selecionou [1, 2, 4] e roteiro tem [1, 2, 3, 4]:
      ✓ Valida: 1, 2, 4
      ✗ Ignora: 3 (com mensagem no resumo)
    - Salva automaticamente: roteiro_original.docx, resultado_validacao.json, resumo.txt
      em: data/clientes/<CNPJ>/submissoes/<YYYYMMDD_HHMMSS>/
    
    Returns:
        {
            "status": "SUCESSO" | "PARCIAL" | "FALHA",
            "timestamp": "2026-07-15T14:30:00",
            "submissao_id": "12345678000190_20260715_143000",
            "log_name": "...",
            "produto_id": "02",
            "testes_selecionados": [1, 2, 4],
            "resumo": {
                "total_selecionados": 3,
                "validados": 2,
                "nao_validados": 1,
                "aprovados": 2,
                "reprovados": 0,
                "percentual_sucesso": 100.0
            },
            "resultados": [...],
            "testes_ignorados": [
                {
                    "teste_id": 3,
                    "motivo": "Não estava na seleção de testes a homologar"
                }
            ]
        }
    """
    
    resultados = []
    testes_ignorados = []
    aprovados = 0
    reprovados = 0
    validados = 0
    
    # Gerar ID de submissão para rastreamento do cliente
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    submissao_id = f"{cnpj}_{timestamp}"
    
    print(f"\n🔄 Iniciando validação em lote")
    print(f"   Submissão ID: {submissao_id}")
    print(f"   Log: {log_name}")
    print(f"   Produto: {produto_id}")
    print(f"   Testes a validar: {len(testes)}")
    if testes_selecionados:
        print(f"   Testes selecionados para homologar: {testes_selecionados}")
    print("-" * 80)

    log_date = _date_from_log_name(log_name)  # ex: "20260803"

    for teste in testes:
        teste_id = teste.get("teste_id")
        bit11 = teste.get("bit11", "").strip()
        bit42 = teste.get("bit42", "").strip()
        
        # Verificar se teste está na seleção
        if testes_selecionados is not None and teste_id not in testes_selecionados:
            print(f"\n⏭️  Teste {teste_id}: NÃO SELECIONADO - Pulando")
            testes_ignorados.append({
                "teste_id": teste_id,
                "motivo": "Não estava na seleção de testes a homologar"
            })
            continue

        # Filtrar por data: ignorar testes cuja data não corresponde ao log
        test_date = _date_from_test(teste.get("data_hora", ""))
        if log_date and test_date and log_date != test_date:
            print(f"\n⏭️  Teste {teste_id}: DATA {test_date} != LOG {log_date} - Pulando")
            testes_ignorados.append({
                "teste_id": teste_id,
                "motivo": f"Data do teste ({test_date[6:]}/{test_date[4:6]}/{test_date[:4]}) não corresponde à data do log ({log_date[6:]}/{log_date[4:6]}/{log_date[:4]})"
            })
            continue
        
        print(f"\n📝 Teste {teste_id}: DE11={bit11}, DE42={bit42}")
        
        if not bit11 or not bit42:
            print(f"   ❌ Dados incompletos - pulando")
            continue
        
        validados += 1
        
        try:
            # Chamar validador
            if _is_autorizador_product(produto_id):
                # CARDSE - usar validator específico
                validacao = validate_log_payload_with_product(
                    produto_id=produto_id,
                    teste_id=str(teste_id),
                    log_name=log_name,
                    de11=bit11,
                    de41=bit42,
                    cliente=cliente,
                    debug=debug,
                )
            else:
                # QR Pago - usar validator padrão
                validacao = validate_log_payload(
                    teste_id=str(teste_id).zfill(2),
                    log_name=log_name,
                    de11=bit11,
                    de41=bit42,
                    cliente=cliente,
                    debug=debug,
                )
            
            # Processar resultado
            is_aprovado = validacao.get("aprovado", False)
            if "status" in validacao and is_aprovado is False:
                is_aprovado = validacao.get("status", "").upper() == "APROVADO"
            
            status = "APROVADO" if is_aprovado else "REPROVADO"
            
            if is_aprovado:
                aprovados += 1
                print(f"   ✅ {status}")
            else:
                reprovados += 1
                _motivos_list = validacao.get("motivos_status_geral", [])
                motivo = _motivos_list[0] if isinstance(_motivos_list, list) and _motivos_list else validacao.get("motivo_negacao", "Falha na valida\u00e7\u00e3o")
                print(f"   ❌ {status}")
                if motivo:
                    print(f"      Motivo: {str(motivo)[:80]}")
            
            # Montar resultado individual
            pernas = validacao.get("pernas", [])
            cadeia = ", ".join(leg.get("mti", "?") for leg in pernas if "mti" in leg)
            
            _ml = validacao.get("motivos_status_geral", [])
            _motivo = _ml[0] if isinstance(_ml, list) and _ml else validacao.get("motivo_negacao", "Sem detalhes")
            _resumo = validacao.get("resumo", {})
            pernas_negadas = [
                {
                    "mti": leg.get("mti", "?"),
                    "motivo": str(leg.get("motivo") or ""),
                }
                for leg in pernas
                if leg.get("aprovado") is False
            ]
            resultado = {
                "teste_id": teste_id,
                "status": status,
                "bit11": bit11,
                "bit42": bit42,
                "resultado_esperado": teste.get("resultado", ""),
                "data_hora": teste.get("data_hora", ""),
                "motivo": str(_motivo) if _motivo else "Sem detalhes",
                "cadeia": cadeia if cadeia else "Nenhuma",
                "pernas_totais": _resumo.get("total_pernas", 0) if isinstance(_resumo, dict) else 0,
                "pernas_aprovadas": _resumo.get("pernas_aprovadas", 0) if isinstance(_resumo, dict) else 0,
                "pernas_negadas_detalhes": pernas_negadas,
            }
            resultados.append(resultado)

            # Salvar log de validação individual no banco
            try:
                from services import db_store as _db
                if _db.is_enabled():
                    _log_lines = [
                        "VALIDAÇÃO EM BATCH — REGISTRO INDIVIDUAL",
                        "=" * 60,
                        f"Produto : {produto_id}",
                        f"CNPJ    : {cnpj}",
                        f"Teste   : {teste_id}",
                        f"BIT 11  : {bit11}",
                        f"BIT 41  : {bit42}",
                        f"Log     : {log_name}",
                        f"Status  : {status}",
                        f"Motivo  : {str(_motivo) if _motivo else '-'}",
                        "-" * 60,
                    ]
                    for p in pernas_negadas:
                        _log_lines.append(f"  Perna {p['mti']} REPROVADA: {p['motivo']}")
                    _db.save_test_log(
                        cnpj=cnpj,
                        produto_id=produto_id,
                        teste_id=str(teste_id),
                        protocolo=submissao_id,
                        status=status,
                        log_content="\n".join(_log_lines),
                    )
            except Exception:
                pass  # log não deve interromper validação
        
        except FileNotFoundError as e:
            print(f"   ⚠️  Log não encontrado: {e}")
            resultados.append({
                "teste_id": teste_id,
                "status": "ERRO",
                "bit11": bit11,
                "bit42": bit42,
                "motivo": f"Log não encontrado: {log_name}",
            })
            reprovados += 1
        
        except Exception as e:
            print(f"   ⚠️  Erro na validação: {e}")
            resultados.append({
                "teste_id": teste_id,
                "status": "ERRO",
                "bit11": bit11,
                "bit42": bit42,
                "motivo": str(e),
            })
            reprovados += 1
    
    # Calcular resumo
    total_selecionados = len(testes_selecionados) if testes_selecionados else len(testes)
    percentual = (aprovados / validados * 100) if validados > 0 else 0
    
    print(f"\n{'=' * 80}")
    print(f"✅ RESUMO DA VALIDAÇÃO")
    print(f"   Total selecionados: {total_selecionados}")
    print(f"   Validados: {validados}")
    print(f"   Não validados (não-selecionados): {len(testes_ignorados)}")
    print(f"   Aprovados: {aprovados}")
    print(f"   Reprovados: {reprovados}")
    print(f"   Taxa de sucesso: {percentual:.2f}%")
    
    # Preparar resposta
    resposta = {
        "status": "SUCESSO" if reprovados == 0 and validados == total_selecionados else "PARCIAL" if aprovados > 0 else "FALHA",
        "timestamp": datetime.now().isoformat(),
        "submissao_id": submissao_id,
        "log_name": log_name,
        "produto_id": produto_id,
        "testes_selecionados": testes_selecionados or [t.get("teste_id") for t in testes],
        "resumo": {
            "total_selecionados": total_selecionados,
            "validados": validados,
            "nao_validados": len(testes_ignorados),
            "aprovados": aprovados,
            "reprovados": reprovados,
            "percentual_sucesso": round(percentual, 2),
        },
        "resultados": resultados,
    }
    
    # Adicionar testes ignorados se houver
    if testes_ignorados:
        resposta["testes_ignorados"] = testes_ignorados
        print(f"\n⚠️  TESTES NÃO VALIDADOS (não selecionados):")
        for teste_ign in testes_ignorados:
            print(f"   - Teste {teste_ign['teste_id']}: {teste_ign['motivo']}")
    
    # Salvar em pasta interna (cliente não tem acesso)
    try:
        _salvar_resultados_interno(cnpj, timestamp, resposta, roteiro_path=roteiro_path)
        print(f"   Resultados salvos para auditoria (submissao_id: {submissao_id})")
    except Exception as e:
        print(f"   ⚠️  Aviso: Não foi possível salvar resultados: {e}")
    
    return resposta
    
    for teste in testes:
        teste_id = teste.get("teste_id")
        bit11 = teste.get("bit11", "").strip()
        bit42 = teste.get("bit42", "").strip()
        
        print(f"\n📝 Teste {teste_id}: DE11={bit11}, DE42={bit42}")
        
        if not bit11 or not bit42:
            print(f"   ❌ Dados incompletos - pulando")
            continue
        
        try:
            # Chamar validador
            if _is_autorizador_product(produto_id):
                # CARDSE - usar validator específico
                validacao = validate_log_payload_with_product(
                    produto_id=produto_id,
                    teste_id=str(teste_id),
                    log_name=log_name,
                    de11=bit11,
                    de41=bit42,
                    cliente=cliente,
                    debug=debug,
                )
            else:
                # QR Pago - usar validator padrão
                validacao = validate_log_payload(
                    teste_id=str(teste_id).zfill(2),
                    log_name=log_name,
                    de11=bit11,
                    de41=bit42,
                    cliente=cliente,
                    debug=debug,
                )
            
            # Processar resultado
            is_aprovado = validacao.get("aprovado", False)
            if "status" in validacao and is_aprovado is False:
                is_aprovado = validacao.get("status", "").upper() == "APROVADO"
            
            status = "APROVADO" if is_aprovado else "REPROVADO"
            
            if is_aprovado:
                aprovados += 1
                print(f"   ✅ {status}")
            else:
                reprovados += 1
                _ml = validacao.get("motivos_status_geral", [])
                motivo = _ml[0] if isinstance(_ml, list) and _ml else validacao.get("motivo_negacao", "Falha na validação")
                print(f"   ❌ {status}")
                if motivo:
                    print(f"      Motivo: {str(motivo)[:80]}")
            
            # Montar resultado individual
            pernas = validacao.get("pernas", [])
            cadeia = ", ".join(leg.get("mti", "?") for leg in pernas if "mti" in leg)
            _motivos_l2 = validacao.get("motivos_status_geral", [])
            _motivo_txt2 = (
                _motivos_l2[0] if isinstance(_motivos_l2, list) and _motivos_l2
                else validacao.get("motivo_negacao", "Sem detalhes")
            )
            _resumo2 = validacao.get("resumo", {})
            resultado = {
                "teste_id": teste_id,
                "status": status,
                "bit11": bit11,
                "bit42": bit42,
                "resultado_esperado": teste.get("resultado", ""),
                "data_hora": teste.get("data_hora", ""),
                "motivo": str(_motivo_txt2) if _motivo_txt2 else "Sem detalhes",
                "cadeia": cadeia if cadeia else "Nenhuma",
                "pernas_totais": _resumo2.get("total_pernas", 0) if isinstance(_resumo2, dict) else 0,
                "pernas_aprovadas": _resumo2.get("pernas_aprovadas", 0) if isinstance(_resumo2, dict) else 0,
                "validacao_resposta": validacao,
            }
            resultados.append(resultado)
        
        except FileNotFoundError as e:
            print(f"   ⚠️  Log não encontrado: {e}")
            resultados.append({
                "teste_id": teste_id,
                "status": "ERRO",
                "bit11": bit11,
                "bit42": bit42,
                "motivo": f"Log não encontrado: {log_name}",
            })
            reprovados += 1
        
        except Exception as e:
            print(f"   ⚠️  Erro na validação: {e}")
            resultados.append({
                "teste_id": teste_id,
                "status": "ERRO",
                "bit11": bit11,
                "bit42": bit42,
                "motivo": str(e),
            })
            reprovados += 1
    
    # Calcular resumo
    total = len(resultados)
    percentual = (aprovados / total * 100) if total > 0 else 0
    
    print(f"\n{'=' * 80}")
    print(f"✅ RESUMO DA VALIDAÇÃO")
    print(f"   Total de testes: {total}")
    print(f"   Aprovados: {aprovados}")
    print(f"   Reprovados: {reprovados}")
    print(f"   Taxa de sucesso: {percentual:.2f}%")
    
    # Preparar resposta
    resposta = {
        "status": "SUCESSO" if reprovados == 0 else "PARCIAL" if aprovados > 0 else "FALHA",
        "timestamp": datetime.now().isoformat(),
        "submissao_id": submissao_id,
        "log_name": log_name,
        "produto_id": produto_id,
        "resumo": {
            "total": total,
            "aprovados": aprovados,
            "reprovados": reprovados,
            "percentual_sucesso": round(percentual, 2),
        },
        "resultados": resultados,
    }
    
    # Salvar em pasta interna (cliente não tem acesso)
    try:
        _salvar_resultados_interno(cnpj, timestamp, resposta, roteiro_path=None)
        print(f"   Resultados salvos para auditoria (submissao_id: {submissao_id})")
    except Exception as e:
        print(f"   ⚠️  Aviso: Não foi possível salvar resultados: {e}")
    
    return resposta


def validar_roteiro_word_batch(
    roteiro_path: str,
    log_name: str,
    produto_id: str = "02",
    cliente: str = "LOCAL",
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Workflow completo: extrai roteiro Word e valida em lote.
    
    Args:
        roteiro_path: Caminho para arquivo Word do roteiro
        log_name: Nome do arquivo de log
        produto_id: ID do produto
        cliente: Identificador do cliente
        debug: Modo debug
    
    Returns:
        Resultado da validação em lote
    """
    
    print(f"\n🎯 WORKFLOW COMPLETO: ROTEIRO + VALIDAÇÃO")
    print(f"   Roteiro: {Path(roteiro_path).name}")
    print(f"   Log: {log_name}")
    
    # Etapa 1: Extrair testes do roteiro
    print(f"\n1️⃣  Extraindo testes do roteiro...")
    testes = parsear_roteiro_docx(roteiro_path)
    
    if not testes:
        return {
            "status": "ERRO",
            "mensagem": f"Nenhum teste com dados completos encontrado no roteiro",
            "timestamp": datetime.now().isoformat(),
        }
    
    # Etapa 2: Validar cada teste
    print(f"\n2️⃣  Validando testes contra log...")
    resultado = validar_roteiro_batch(
        log_name=log_name,
        testes=testes,
        produto_id=produto_id,
        cliente=cliente,
        debug=debug,
    )
    
    return resultado


def _salvar_resultados_interno(
    cnpj: str,
    timestamp: str,
    resultado: Dict[str, Any],
    roteiro_path: Optional[str] = None,
) -> str:
    """
    Salva resultados em pasta interna do cliente para auditoria.
    Cliente NÃO tem acesso a essa pasta.
    
    Args:
        cnpj: CNPJ do cliente
        timestamp: Timestamp da submissão (YYYYMMDD_HHMMSS)
        resultado: Dicionário com resultados da validação
        roteiro_path: Caminho do arquivo roteiro para copiar (opcional)
    
    Returns:
        Caminho da pasta criada
    """
    # Criar estrutura de pastas
    pasta_cliente = Path(f"data/clientes/{cnpj}/submissoes/{timestamp}")
    pasta_cliente.mkdir(parents=True, exist_ok=True)
    
    # Salvar resultado_validacao.json
    arquivo_json = pasta_cliente / "resultado_validacao.json"
    with open(arquivo_json, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    
    # Gerar e salvar resumo.txt (human-readable)
    arquivo_resumo = pasta_cliente / "resumo.txt"
    resumo_texto = _gerar_resumo_texto(resultado)
    with open(arquivo_resumo, 'w', encoding='utf-8') as f:
        f.write(resumo_texto)
    
    # Copiar roteiro original se fornecido
    if roteiro_path:
        roteiro_path_obj = Path(roteiro_path)
        if roteiro_path_obj.exists():
            import shutil
            arquivo_roteiro = pasta_cliente / "roteiro_original.docx"
            shutil.copy2(roteiro_path, str(arquivo_roteiro))
    
    return str(pasta_cliente)


def _gerar_resumo_texto(resultado: Dict[str, Any]) -> str:
    """Gera resumo em formato texto (human-readable) a partir dos resultados."""
    
    resumo = resultado.get("resumo", {})
    resultados = resultado.get("resultados", [])
    testes_ignorados = resultado.get("testes_ignorados", [])
    
    linhas = [
        "═" * 70,
        " " * 15 + "RELATÓRIO DE VALIDAÇÃO EM BATCH",
        "═" * 70,
        "",
        f"Data/Hora:              {resultado.get('timestamp', 'N/A')}",
        f"Submissão ID:           {resultado.get('submissao_id', 'N/A')}",
        f"Produto:                {resultado.get('produto_id', 'N/A')} (CARDSE)" if resultado.get('produto_id') == '02' else f"Produto:                {resultado.get('produto_id', 'N/A')} (QR Pago)",
        f"Log Validado:           {resultado.get('log_name', 'N/A')}",
        f"Testes Selecionados:    {', '.join(str(t) for t in resultado.get('testes_selecionados', []))}",
        "",
        "─" * 70,
        "RESUMO EXECUTIVO",
        "─" * 70,
        "",
        f"Total Selecionados:                {resumo.get('total_selecionados', 0)}",
        f"Total Validados:                   {resumo.get('validados', 0)}",
        f"✅ Aprovados:                      {resumo.get('aprovados', 0)}",
        f"❌ Reprovados:                     {resumo.get('reprovados', 0)}",
        f"📈 Taxa de Sucesso:                {resumo.get('percentual_sucesso', 0):.2f}%",
        "",
        "─" * 70,
        "DETALHES POR TESTE",
        "─" * 70,
    ]
    
    # Separar testes aprovados e reprovados
    aprovados_testes = [t for t in resultados if t.get("status") == "APROVADO"]
    reprovados_testes = [t for t in resultados if t.get("status") != "APROVADO"]
    
    if aprovados_testes:
        linhas.append(f"\n✅ TESTES APROVADOS ({len(aprovados_testes)}):\n")
        for teste in aprovados_testes:
            linhas.append(f"  Teste {str(teste.get('teste_id')).zfill(2)}: APROVADO ✓")
            linhas.append(f"    BIT 11 (Stan): {teste.get('bit11')}")
            linhas.append(f"    BIT 42 (Estab): {teste.get('bit42')}")
            if teste.get('cadeia') and teste.get('cadeia') != 'Nenhuma':
                linhas.append(f"    Cadeia: {teste.get('cadeia')}")
            linhas.append(f"    Pernas: {teste.get('pernas_aprovadas', 0)}/{teste.get('pernas_totais', 0)} aprovadas")
            linhas.append("")
    
    if reprovados_testes:
        linhas.append(f"\n❌ TESTES REPROVADOS ({len(reprovados_testes)}):\n")
        for teste in reprovados_testes:
            linhas.append(f"  Teste {str(teste.get('teste_id')).zfill(2)}: REPROVADO ✗")
            linhas.append(f"    BIT 11 (Stan): {teste.get('bit11')}")
            linhas.append(f"    BIT 42 (Estab): {teste.get('bit42')}")
            if teste.get("motivo"):
                linhas.append(f"    ⚠️  Motivo: {teste.get('motivo')}")
            if teste.get('cadeia') and teste.get('cadeia') != 'Nenhuma':
                linhas.append(f"    Cadeia: {teste.get('cadeia')}")
            linhas.append(f"    Pernas: {teste.get('pernas_aprovadas', 0)}/{teste.get('pernas_totais', 0)} aprovadas")
            linhas.append("")
    
    # Testes ignorados
    if testes_ignorados:
        linhas.append(f"\n⏭️  TESTES NÃO VALIDADOS ({len(testes_ignorados)}):\n")
        for teste_ign in testes_ignorados:
            linhas.append(f"  Teste {str(teste_ign['teste_id']).zfill(2)}: NÃO VALIDADO")
            linhas.append(f"    Motivo: {teste_ign['motivo']}")
            linhas.append("")
    
    linhas.extend([
        "",
        "─" * 70,
        "AÇÕES RECOMENDADAS",
        "─" * 70,
        "",
    ])
    
    # Adicionar recomendações baseadas em resultados
    reprovados_count = resumo.get('reprovados', 0)
    if reprovados_count > 0:
        linhas.append(f"1. {reprovados_count} teste(s) falharam - Revise os detalhes acima")
        linhas.append("2. Corrija os dados dos testes falhados")
        linhas.append("3. Resubmeta o roteiro com as correções")
    else:
        linhas.append("✅ Todos os testes selecionados foram aprovados!")
        linhas.append("   Próximo passo: Submeter para aprovação final")
    
    linhas.extend([
        "",
        "═" * 70,
    ])
    
    return "\n".join(linhas)


def salvar_resultado_batch(resultado: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """
    Salva resultado da validação em batch em arquivo JSON.
    
    Args:
        resultado: Dicionário com resultado
        output_path: Caminho do arquivo (default: data/roteiros/batch_resultados_<timestamp>.json)
    
    Returns:
        Caminho do arquivo salvo
    """
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/roteiros/batch_resultados_{timestamp}.json"
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    
    return output_path


if __name__ == "__main__":
    # Teste do workflow completo
    roteiro_file = "data/roteiros/Roteiro de Homologação FepasCardSE_Cartão (Autorizador) _Versão Cliente 1.9.docx"
    log_file = "logs/CARDSE_AUTORIZADOR_20260704_094000.fps.txt"  # Exemplo
    
    print("\n" + "=" * 80)
    print("BATCH VALIDATION TEST")
    print("=" * 80)
    
    try:
        # Validação em batch
        resultado = validar_roteiro_word_batch(
            roteiro_path=roteiro_file,
            log_name=Path(log_file).name,
            produto_id="02",
            cliente="LOCAL",
            debug=True,
        )
        
        # Salvar resultado
        output_file = salvar_resultado_batch(resultado)
        print(f"\n💾 Resultado salvo em: {output_file}")
        
        # Mostrar resumo JSON
        print(f"\n📊 RESULTADO (JSON):")
        print(json.dumps(resultado["resumo"], indent=2))
        
    except FileNotFoundError as e:
        print(f"❌ Erro: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
