# products_config.py
"""
Configuração de produtos suportados para homologação.
Define qual roteiro e validador usar para cada produto.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Callable

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
ROTEIROS_DIR = BASE_DIR / "data" / "roteiros"

PRODUTOS = {
    "01_QRCARDSE": {
        "id": "01_QRCARDSE",
        "nome": "Homologação QR Pago",
        "descricao": "Validador para transações QR Pago com fluxos completos",
        "roteiro_path": str(ROTEIROS_DIR / "roteiro_iso_0200.json"),
        "validador_module": "validador_0200",
        "validador_function": "avaliar_teste_homologacao_web",
        "tipo_validacao": "bidirecionais",  # Valida FEPAS -> PROCESSADORA e PROCESSADORA -> FEPAS
    },
    "02_AutorizadorCARDSE": {
        "id": "02_AutorizadorCARDSE",
        "nome": "Homologação Autorizador",
        "descricao": "Validador para Autorizador CARDSE - valida TERMINAL > FEPAS (BIT 22) e PROC > FEPAS (todos os campos)",
        "roteiro_path": str(ROTEIROS_DIR / "roteiro_iso_novo_produto.json"),
        "validador_module": "validador_cardse",
        "validador_function": "validar_mensagens_processadora",
        "tipo_validacao": "bidirecionais",  # Valida TERMINAL -> FEPAS e PROC -> FEPAS
    },
}


def get_produto(produto_id: str) -> Dict[str, Any]:
    """Obtém configuração do produto by ID."""
    produto_id = str(produto_id or "").strip()
    # Se receber número simples, converter para nome descritivo
    if produto_id == "01" or produto_id == "1":
        produto_id = "01_QRCARDSE"
    elif produto_id == "02" or produto_id == "2":
        produto_id = "02_AutorizadorCARDSE"
    
    if produto_id not in PRODUTOS:
        raise ValueError(
            f"Produto '{produto_id}' não encontrado. "
            f"Produtos disponíveis: {', '.join(sorted(PRODUTOS.keys()))}"
        )
    return PRODUTOS[produto_id]


def listar_produtos() -> list:
    """Lista todos os produtos disponíveis."""
    return [
        {
            "id": v.get("id"),
            "nome": v.get("nome"),
            "descricao": v.get("descricao"),
            "tipo_validacao": v.get("tipo_validacao"),
        }
        for v in sorted(PRODUTOS.values(), key=lambda x: x.get("id", ""))
    ]


def get_roteiro_path(produto_id: str) -> str:
    """Obtém o caminho do roteiro para um produto."""
    produto = get_produto(produto_id)
    return produto["roteiro_path"]


def get_validador_info(produto_id: str) -> Dict[str, str]:
    """Obtém informações do validador para um produto."""
    produto = get_produto(produto_id)
    return {
        "module": produto["validador_module"],
        "function": produto["validador_function"],
    }
