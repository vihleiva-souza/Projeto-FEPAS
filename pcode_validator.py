"""
Validador de Pcode (Bit 03) para produto QR Pago.
Extrai e valida o Processing Code (Bit 03) conforme regras do roteiro.
"""

from typing import Dict, Tuple, Optional


def extract_bit03_pcode(campos: Dict[str, str]) -> str:
    """
    Extrai o Pcode do Bit 03 de um dicionário de campos ISO 8583.

    Args:
        campos: dicionário com campos da mensagem (ex: {"03": "003000"})

    Returns:
        String com o valor do Bit 03 ou "" se ausente.
    """
    return str(campos.get("03") or campos.get("3") or "").strip()


def validate_pcode_for_product_type(
    pcode: str,
    product_type: str,
    pcode_rules: Dict,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valida se o Pcode é permitido para o product_type informado,
    usando as regras configuradas no roteiro JSON.

    Args:
        pcode:        Valor do Bit 03 extraído da mensagem.
        product_type: Tipo do produto (ex: "credito", "debito", "voucher", etc.)
        pcode_rules:  Dicionário de regras do roteiro (chave "pcode_rules").

    Returns:
        (is_valid, error_msg, description)
        - is_valid:    True se válido
        - error_msg:   Mensagem de erro (None se válido)
        - description: Descrição do pcode encontrado (None se não mapeado)
    """
    if not pcode_rules or not pcode_rules.get("enabled"):
        # Validação de pcode desabilitada no roteiro → sempre válido
        return True, None, None

    mappings: Dict = pcode_rules.get("mappings", {})

    # Procurar pcode no mapeamento
    pcode_info = mappings.get(pcode)
    if not pcode_info:
        # Pcode não mapeado → permitir (modo permissivo)
        return True, None, None

    description = pcode_info.get("description", "")
    allowed_types = pcode_info.get("product_types", [])

    if not allowed_types:
        # Sem restrição de product_type → sempre válido
        return True, None, description

    if product_type in allowed_types:
        return True, None, description

    error_msg = (
        f"Pcode '{pcode}' ({description}) não é válido para produto '{product_type}'. "
        f"Tipos permitidos: {', '.join(allowed_types)}."
    )
    return False, error_msg, description
