"""
Parser para extrair testes do roteiro Word do cliente.
Formato esperado: Coluna "Evidencia dos Testes" com estrutura:
    Resultado: <valor>
    Data/Hora: <valor>
    BIT 11: <valor>
    BIT 42: <valor>
"""

import zipfile
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import List, Dict, Any


def parsear_roteiro_docx(file_path: str) -> List[Dict[str, Any]]:
    """
    Extrai testes do arquivo Word do cliente.
    
    Args:
        file_path: Caminho para o arquivo .docx
        
    Returns:
        Lista de testes com dados completos (resultado, data_hora, bit11, bit42)
        Apenas testes com BIT 11 e BIT 42 preenchidos são inclusos.
    """
    doc_path = Path(file_path)
    
    if not doc_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    
    testes = []
    
    try:
        # Ler document.xml do .docx (é um ZIP)
        with zipfile.ZipFile(doc_path, 'r') as zip_ref:
            xml_content = zip_ref.read('word/document.xml')
        
        # Parse XML
        root = ET.fromstring(xml_content)
        
        # Namespace do Word
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        # Extrair todas as tabelas
        tables = root.findall('.//w:tbl', ns)
        
        print(f"Total de tabelas encontradas: {len(tables)}")
        
        # Procurar pela tabela "Sequência de testes" (procura por "Seq." no header)
        for table_idx, table in enumerate(tables):
            rows = table.findall('.//w:tr', ns)
            
            if not rows or len(rows) < 3:  # Precisa ter pelo menos header + 1 dado
                continue
            
            # Procurar por header com "Seq."
            header_row_idx = None
            for check_row_idx in range(min(3, len(rows))):
                cells = rows[check_row_idx].findall('.//w:tc', ns)
                if cells:
                    first_cell_text = _extract_cell_text(cells[0], ns).strip()
                    if first_cell_text == "Seq.":
                        header_row_idx = check_row_idx
                        break
            
            if header_row_idx is not None:
                # Encontrar coluna de evidências
                header_cells = rows[header_row_idx].findall('.//w:tc', ns)
                col_evidencia_idx = None
                
                for col_idx, cell in enumerate(header_cells):
                    cell_text = _extract_cell_text(cell, ns).strip().lower()
                    if "evidência" in cell_text or "evidencia" in cell_text:
                        col_evidencia_idx = col_idx
                        break
                
                if col_evidencia_idx is not None:
                    print(f"\n📋 Tabela {table_idx}: 'Sequência de testes' encontrada")
                    print(f"   Header na linha {header_row_idx}")
                    print(f"   Coluna de Evidências: índice {col_evidencia_idx}")
                    print(f"   Total de linhas de dados: {len(rows) - header_row_idx - 1}")
                    
                    # Processar cada linha de dados (exceto header)
                    # Número do teste é inferido pela posição (primeira = 1)
                    teste_counter = 1
                    for row_idx, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 1):
                        cells = row.findall('.//w:tc', ns)
                        
                        if col_evidencia_idx < len(cells):
                            evidencia_text = _extract_cell_text(cells[col_evidencia_idx], ns)
                            
                            # Parsear campos da evidência
                            teste_data = _parsear_evidencia(evidencia_text, teste_counter)
                            
                            if teste_data and teste_data.get("bit11") and teste_data.get("bit42"):
                                testes.append(teste_data)
                                print(f"   ✓ Teste {teste_data['teste_id']}: {teste_data['resultado']}")
                        
                        teste_counter += 1
    
    except zipfile.BadZipFile:
        raise ValueError(f"Arquivo não é um documento Word válido: {file_path}")
    except Exception as e:
        raise Exception(f"Erro ao processar documento: {e}")
    
    print(f"\n✅ Total de testes com dados completos: {len(testes)}")
    return testes


def _extract_cell_text(cell, ns: Dict[str, str]) -> str:
    """Extrai todo o texto de uma célula da tabela."""
    texts = []
    for text_elem in cell.findall('.//w:t', ns):
        if text_elem.text:
            texts.append(text_elem.text)
    return ''.join(texts)


def _parsear_evidencia(evidencia_text: str, teste_id: int = None) -> Dict[str, Any]:
    """
    Parseia o bloco de evidência com formatos flexíveis:
        Resultado: <valor>
        Data/Hora: <valor>
        BIT 11: <valor>
        BIT 42: <valor>
    
    Pode estar em linhas separadas ou concatenado sem quebra de linha.
    
    Args:
        evidencia_text: Texto bruto da célula de evidência
        teste_id: ID do teste (se já extraído da coluna de teste)
        
    Returns:
        Dicionário com os dados extraídos ou None se inválido
    """
    if not evidencia_text.strip():
        return None
    
    # Normalizar: adicionar quebra de linha antes de cada label conhecido
    normalized = evidencia_text
    for label in ["Resultado:", "Data/Hora", "BIT 11:", "BIT 42:"]:
        # Se a label não está no início de uma linha, adicionar quebra antes
        normalized = normalized.replace(label, f"\n{label}")
    
    resultado = None
    data_hora = None
    bit11 = None
    bit42 = None
    
    # Dividir por linhas
    lines = normalized.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Resultado
        if line.lower().startswith('resultado:'):
            resultado = line.split(':', 1)[1].strip() if ':' in line else None
        
        # Data/Hora (várias variações)
        elif 'data' in line.lower() and 'hora' in line.lower():
            if ':' in line:
                data_hora = line.split(':', 1)[1].strip()
            else:
                data_hora = line
        
        # BIT 11
        elif 'bit' in line.lower() and '11' in line:
            if ':' in line:
                bit11 = line.split(':', 1)[1].strip()
            else:
                bit11 = line.replace('BIT 11', '').replace('BIT11', '').strip()
        
        # BIT 42
        elif 'bit' in line.lower() and '42' in line:
            if ':' in line:
                bit42 = line.split(':', 1)[1].strip()
            else:
                bit42 = line.replace('BIT 42', '').replace('BIT42', '').strip()
    
    # Validar: precisa de bit11 e bit42 não vazios
    if not (bit11 and bit11.strip()) or not (bit42 and bit42.strip()):
        return None
    
    return {
        "teste_id": teste_id,
        "resultado": (resultado or "").strip(),
        "data_hora": (data_hora or "").strip(),
        "bit11": bit11.strip(),
        "bit42": bit42.strip(),
    }


if __name__ == "__main__":
    # Teste do parser
    docx_path = Path('data/roteiros/Roteiro de Homologação FepasCardSE_Cartão (Autorizador) _Versão Cliente 1.9.docx')
    temp_path = Path('data/roteiros/roteiro_temp.docx')
    
    # Se arquivo original está bloqueado, usar cópia temporária
    if temp_path.exists():
        docx_path = temp_path
        print(f"📌 Usando cópia temporária: {temp_path.name}\n")
    
    print(f"🔍 Parseando: {docx_path.name}\n")
    print("=" * 80)
    
    try:
        testes = parsear_roteiro_docx(str(docx_path))
        
        print("\n" + "=" * 80)
        print("\n📊 TESTES EXTRAÍDOS:")
        print("-" * 80)
        
        for teste in testes[:10]:  # Mostrar primeiros 10
            print(f"\nTeste {teste['teste_id']}:")
            print(f"  Resultado: {teste['resultado']}")
            print(f"  Data/Hora: {teste['data_hora']}")
            print(f"  BIT 11:    {teste['bit11']}")
            print(f"  BIT 42:    {teste['bit42']}")
        
        if len(testes) > 10:
            print(f"\n... e mais {len(testes) - 10} testes")
        
        # Salvar em JSON para referência
        import json
        output_file = Path('data/roteiros/testes_cliente_extraidos.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(testes, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Testes salvos em: {output_file}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
