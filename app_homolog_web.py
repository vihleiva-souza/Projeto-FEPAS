from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request, url_for

import homolog_service
from services import homolog_service_multiproduct as homolog_service_mp
from services import db_store

BASE_DIR = homolog_service.BASE_DIR
get_log_summary_payload = homolog_service.get_log_summary_payload
get_tests_payload = homolog_service.get_tests_payload
list_logs_payload = homolog_service.list_logs_payload
validate_log_payload = homolog_service.validate_log_payload
get_health_payload = homolog_service.get_health_payload
get_api_config_payload = homolog_service.get_api_config_payload

# NOTE: Removed old non-product functions to avoid creating folders outside product directories
# - list_clients_payload (deprecated, use list_clients_payload_multiproduct)
# - get_client_progress_payload (deprecated, use get_client_progress_payload_for_product)
# - admin_set_client_tests, admin_reset_client_onboarding, admin_reset_client_tests (deprecated, use -for_product versions)

# Multiproduct functions
get_api_config_with_products = homolog_service_mp.get_api_config_with_products
get_tests_payload_for_product = homolog_service_mp.get_tests_payload_for_product
validate_log_payload_with_product = homolog_service_mp.validate_log_payload_with_product
validate_client_payload_with_product = homolog_service_mp.validate_client_payload_with_product
enroll_client_tests_for_product = homolog_service_mp.enroll_client_tests_for_product
get_client_progress_payload_for_product = homolog_service_mp.get_client_progress_payload_for_product
get_client_progress_payload_all_products = homolog_service_mp.get_client_progress_payload_all_products
list_clients_payload_multiproduct = homolog_service_mp.list_clients_payload_multiproduct
admin_set_client_tests_for_product = homolog_service_mp.admin_set_client_tests_for_product
admin_reset_client_onboarding_for_product = homolog_service_mp.admin_reset_client_onboarding_for_product
admin_reset_client_tests_for_product = homolog_service_mp.admin_reset_client_tests_for_product
fetch_logs_for_product_by_date = homolog_service_mp.fetch_logs_for_product_by_date

# Importar função de listagem de produtos diretamente
from products_config import listar_produtos

def normalize_produto_id(produto_id: str) -> str:
    """Normaliza produto_id para formato descritivo (01_QRCARDSE ou 02_AutorizadorCARDSE)."""
    normalized = str(produto_id or "01").strip()
    # Se for o formato completo, retorna como está
    if normalized in ("01_QRCARDSE", "02_AutorizadorCARDSE"):
        return normalized
    # Se for número, converte
    if normalized in ("01", "1"):
        return "01_QRCARDSE"
    if normalized in ("02", "2"):
        return "02_AutorizadorCARDSE"
    # Padrão
    return "01_QRCARDSE"

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.config["SECRET_KEY"] = os.environ.get("HOMOLOG_SECRET_KEY", "homolog-stage2-local-secret")

# Force Render deployment: 2026-07-20 10:30:00
print("[APP] Inicializando app_homolog_web com endpoint /api/admin/logs/upload ativo")

# Log all registered routes at startup
_admin_routes = [str(r) for r in app.url_map.iter_rules() if 'admin' in str(r) or 'upload' in str(r)]
print(f"[APP] Rotas admin/upload registradas: {_admin_routes}")

db_store.init_db()


@app.get("/diagnostico")
def diagnostico():
    """Endpoint para diagnosticar rotas registradas."""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "rule": str(rule),
            "methods": list(rule.methods - {"OPTIONS", "HEAD"}),
        })
    return jsonify({
        "status": "ok",
        "total_routes": len(routes),
        "admin_routes": [r for r in routes if "admin" in r["rule"] or "upload" in r["rule"]],
    })


@app.get("/")
def home():
    return render_template("portal_entry.html")


@app.get("/interno")
def internal_home():
    return render_template("index.html")


@app.get("/cliente")
def client_home():
    return render_template("client.html")


@app.get("/api/tests")
def get_tests():
    return jsonify(get_tests_payload())


@app.get("/api/logs")
def get_logs():
    return jsonify(list_logs_payload())


@app.post("/api/produtos/<produto_id>/logs/fetch-by-date")
def fetch_logs_by_date_for_product(produto_id: str):
    """Dispara coleta de logs por data para o produto informado."""
    payload = request.get_json(silent=True) or {}
    data_teste = str(payload.get("data_teste") or request.form.get("data_teste") or "").strip()
    force_raw = payload.get("force", request.form.get("force", False))
    force = str(force_raw).strip().lower() in {"1", "true", "yes", "sim"}

    try:
        result = fetch_logs_for_product_by_date(
            produto_id=normalize_produto_id(produto_id),
            data_teste=data_teste,
            force=force,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao coletar logs por data: {exc}"}), 500


@app.post("/api/admin/logs/upload")
def admin_upload_log():
    """Upload administrativo de log de auditoria. Protegido por HOMOLOG_ADMIN_KEY."""
    from services.homolog_service import LOGS_DIR

    # Autenticação por API key
    admin_key = os.environ.get("HOMOLOG_ADMIN_KEY", "")
    if admin_key:
        provided = (
            request.headers.get("X-Admin-Key", "")
            or request.form.get("admin_key", "")
        )
        if provided != admin_key:
            return jsonify({"error": "Nao autorizado"}), 401

    produto_id = str(request.form.get("produto_id") or "").strip()
    data_teste = str(request.form.get("data_teste") or "").strip()

    if not produto_id:
        return jsonify({"error": "Campo produto_id obrigatorio"}), 400
    if not data_teste:
        return jsonify({"error": "Campo data_teste obrigatorio (formato YYYYMMDD)"}), 400

    data_teste = data_teste.replace("-", "").replace("/", "").strip()
    if len(data_teste) != 8 or not data_teste.isdigit():
        return jsonify({"error": "data_teste invalido. Use YYYYMMDD"}), 400

    if "log_file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado. Use o campo 'log_file'"}), 400

    uploaded = request.files["log_file"]
    if not uploaded.filename:
        return jsonify({"error": "Arquivo sem nome"}), 400

    if not uploaded.filename.lower().endswith(".txt"):
        return jsonify({"error": "Apenas arquivos .txt sao aceitos"}), 400

    pid = normalize_produto_id(produto_id)
    dest_dir = LOGS_DIR / pid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"aud_{data_teste}.txt"

    uploaded.save(str(dest_path))
    size_mb = dest_path.stat().st_size / 1024 / 1024

    return jsonify({
        "success": True,
        "message": f"Log salvo: {pid} / {data_teste}",
        "path": str(dest_path),
        "size_mb": round(size_mb, 2),
    })


@app.get("/api/health")
def get_health():
    payload = get_health_payload()
    payload["app_version"] = "20260720-v5-with-upload"
    return jsonify(payload)


@app.get("/api/config")
def get_config():
    return jsonify(get_api_config_payload())


@app.get("/api/produtos")
def get_produtos():
    """Lista produtos disponíveis para homologação."""
    try:
        return jsonify({"produtos": listar_produtos()})
    except Exception as exc:
        return jsonify({"error": f"Erro ao listar produtos: {exc}"}), 500


@app.get("/api/produtos/<produto_id>/tests")
def get_tests_for_product(produto_id: str):
    """Obtém testes disponíveis para um produto específico.
    
    Query parameters:
    - cnpj: (opcional) Se fornecido, retorna apenas testes designados para esse CNPJ
    """
    try:
        cnpj = request.args.get("cnpj", "").strip() or None
        result = get_tests_payload_for_product(produto_id, cnpj=cnpj)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Erro ao obter testes: {exc}"}), 500


@app.get("/api/logs/<path:log_name>/summary")
def get_log_summary(log_name: str):
    try:
        return jsonify(get_log_summary_payload(log_name))
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        status = 413 if "excede o limite" in str(exc) else 400
        return jsonify({"error": str(exc)}), status


@app.post("/api/validate")
def validate_log():
    try:
        result = validate_log_payload(
            teste_id=str(request.form.get("teste_id") or "").strip(),
            log_name=str(request.form.get("log_name") or "").strip(),
            de11=str(request.form.get("de11") or "").strip(),
            de41=str(request.form.get("de41") or "").strip(),
            cliente="LOCAL",
            debug=False,
        )
    except ValueError as exc:
        status = 413 if "excede o limite" in str(exc) else 400
        return jsonify({"error": str(exc)}), status
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao validar log: {exc}"}), 500

    return jsonify(result)


@app.post("/api/validate-produto")
def validate_log_with_product():
    """Valida log com seleção de produto."""
    try:
        produto_id = normalize_produto_id(request.form.get("produto_id") or "01")
        _de_filtro = str(request.form.get("de42" if produto_id == "02_AutorizadorCARDSE" else "de41") or "").strip()
        result = validate_log_payload_with_product(
            produto_id=produto_id,
            teste_id=str(request.form.get("teste_id") or "").strip(),
            log_name=str(request.form.get("log_name") or "").strip(),
            de11=str(request.form.get("de11") or "").strip(),
            de41=_de_filtro,
            cliente="LOCAL",
            debug=False,
        )
    except ValueError as exc:
        status = 413 if "excede o limite" in str(exc) else 400
        return jsonify({"error": str(exc)}), status
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao validar log: {exc}"}), 500

    return jsonify(result)


@app.post("/api/client/validate-produto")
def validate_client_with_product():
    """Valida cliente com seleção de produto."""
    try:
        produto_id = normalize_produto_id(request.form.get("produto_id") or "01")
        product_type = str(request.form.get("product_type") or "credito_debito").strip()
        comunicacao_tipo = str(request.form.get("comunicacao_tipo") or "ISO").strip()
        _de_filtro = str(request.form.get("de42" if produto_id == "02_AutorizadorCARDSE" else "de41") or "").strip()
        result = validate_client_payload_with_product(
            produto_id=produto_id,
            product_type=product_type,
            cnpj=str(request.form.get("cnpj") or "").strip(),
            data_teste=str(request.form.get("data_teste") or "").strip(),
            teste_id=str(request.form.get("teste_id") or "").strip(),
            de11=str(request.form.get("de11") or "").strip(),
            de41=_de_filtro,
            comunicacao_tipo=comunicacao_tipo,
        )
    except ValueError as exc:
        status = 413 if "excede o limite" in str(exc) else 400
        return jsonify({"error": str(exc)}), status
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao processar homologação do cliente: {exc}"}), 500

    return jsonify(result)


@app.post("/api/client/enroll-produto")
def enroll_client_with_product():
    """Registra testes designados para um CNPJ no produto selecionado."""
    try:
        selected_tests = request.form.getlist("selected_tests")
        payload = request.get_json(silent=True) or {}
        if not selected_tests:
            selected_tests = list(payload.get("selected_tests") or [])

        produto_id = normalize_produto_id(request.form.get("produto_id") or payload.get("produto_id") or "01")
        cnpj = str(request.form.get("cnpj") or payload.get("cnpj") or "").strip()

        result = enroll_client_tests_for_product(
            cnpj=cnpj,
            produto_id=produto_id,
            selected_test_ids=selected_tests,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao registrar testes do cliente: {exc}"}), 500

    return jsonify(result)


@app.post("/api/validar-roteiro-cliente-batch")
def validate_roteiro_cliente_batch():
    """
    Validação em batch: cliente faz upload do roteiro Word e log.
    O sistema extrai testes, valida APENAS os selecionados contra o log.
    
    Parâmetros de entrada (multipart/form-data):
    - roteiro_file: Arquivo Word (.docx) com roteiro do cliente
    - log_name: Nome do arquivo de log (já disponível no sistema)
    - produto_id: ID do produto (default "02" para CARDSE)
    - cnpj: CNPJ do cliente
    - testes_selecionados: JSON com IDs dos testes a validar (ex: [1, 2, 4])
                          Se vazio/ausente, valida todos
    
    Comportamento:
    - Se cliente selecionou [1, 2, 4] mas roteiro tem [1, 2, 3, 4]:
      ✓ Valida: 1, 2, 4
      ⏭️  Ignora: 3 (com motivo no resumo)
    
    Resposta (JSON):
    {
        "status": "SUCESSO" | "PARCIAL" | "FALHA",
        "timestamp": "2026-07-15T14:30:00",
        "submissao_id": "12345678000190_20260715_143000",
        "testes_selecionados": [1, 2, 4],
        "resumo": {
            "total_selecionados": 3,
            "validados": 3,
            "nao_validados": 1,
            "aprovados": 3,
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
    from roteiro_batch_validator import (
        parsear_roteiro_docx,
        validar_roteiro_batch,
    )
    from pathlib import Path
    import tempfile
    import json
    
    try:
        # Validar parâmetros
        roteiro_file = request.files.get("roteiro_file")
        log_name = str(request.form.get("log_name") or "").strip()
        produto_id = normalize_produto_id(request.form.get("produto_id") or "02")
        cnpj = str(request.form.get("cnpj") or "LOCAL").strip()
        testes_selecionados_str = str(request.form.get("testes_selecionados") or "").strip()
        
        if not roteiro_file:
            return jsonify({"error": "Campo 'roteiro_file' é obrigatório"}), 400
        if not log_name:
            return jsonify({"error": "Campo 'log_name' é obrigatório"}), 400
        if cnpj == "LOCAL":
            return jsonify({"error": "Campo 'cnpj' é obrigatório"}), 400
        
        # Parsear testes selecionados
        testes_selecionados = None
        if testes_selecionados_str:
            try:
                # Aceita formato: [1,2,3] ou 1,2,3
                testes_selecionados_str = testes_selecionados_str.strip("[]")
                testes_selecionados = [int(x.strip()) for x in testes_selecionados_str.split(",")]
            except (ValueError, AttributeError):
                return jsonify({"error": "Formato inválido para 'testes_selecionados'. Use: [1,2,3]"}), 400
        
        # Salvar arquivo temporário na pasta temp/
        temp_dir = BASE_DIR / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        original_filename = str(getattr(roteiro_file, "filename", "roteiro_cliente.docx") or "roteiro_cliente.docx")
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False, dir=str(temp_dir)) as tmp:
            roteiro_file.save(tmp.name)
            temp_roteiro_path = tmp.name
        
        # Etapa 1: Extrair testes do roteiro
        testes = parsear_roteiro_docx(temp_roteiro_path)
        
        if not testes:
            Path(temp_roteiro_path).unlink(missing_ok=True)
            return jsonify({
                "error": "Nenhum teste com dados completos encontrado no roteiro",
                "detalhes": "O roteiro deve ter testes com BIT 11 e BIT 42 preenchidos"
            }), 400
        
        # Etapa 2: Validar em batch (apenas testes selecionados)
        resultado_batch = validar_roteiro_batch(
            log_name=log_name,
            testes=testes,
            cnpj=cnpj,
            testes_selecionados=testes_selecionados,
            produto_id=produto_id,
            cliente=cnpj,
            roteiro_path=temp_roteiro_path,
            debug=False,
        )

        if db_store.is_enabled():
            roteiro_bytes = Path(temp_roteiro_path).read_bytes()
            db_store.save_roteiro_submission(
                submissao_id=str(resultado_batch.get("submissao_id") or ""),
                cnpj=cnpj,
                produto_id=produto_id,
                log_name=log_name,
                roteiro_filename=original_filename,
                roteiro_content=roteiro_bytes,
                result=resultado_batch,
            )
        
        # Limpeza (APÓS validação, que já salvou o roteiro)
        Path(temp_roteiro_path).unlink(missing_ok=True)
        
        # Retornar JSON (sem expor caminhos de pasta)
        return jsonify(resultado_batch)
    
    except FileNotFoundError as exc:
        return jsonify({"error": f"Log não encontrado: {exc}"}), 404
    except ValueError as exc:
        return jsonify({"error": f"Erro de validação: {exc}"}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao validar roteiro em batch: {exc}"}), 500


@app.get("/api/testes-disponiveis/<produto_id>")
def get_testes_disponiveis(produto_id: str):
    """
    Retorna a lista de testes disponíveis para um produto.
    Usado pelo portal para popular o seletor de checkboxes.
    
    Exemplo de resposta:
    {
        "produto_id": "02",
        "produto_nome": "Homologação Autorizador",
        "testes": [
            {"id": 1, "label": "Teste 1"},
            {"id": 2, "label": "Teste 2"},
            ...
            {"id": 55, "label": "Teste 55"}
        ]
    }
    """
    try:
        produto_id = str(produto_id or "").strip().zfill(2)

        produto_config = {
            "01": {"nome": "Homologação QR Pago"},
            "02": {"nome": "Homologação Autorizador"},
        }

        if produto_id not in produto_config:
            return jsonify({"error": f"Produto '{produto_id}' não encontrado"}), 404
        
        # Obter info do produto
        produto_config = {
            "01": {"nome": "Homologação QR Pago"},
            "02": {"nome": "Homologação Autorizador"},
        }

        tests_data = get_tests_payload_for_product(produto_id)
        testes = [
            {
                "id": int(t["id"]),
                "label": f"{t['id']} - {t['nome']}" if t.get("nome") else f"Teste {t['id']}",
            }
            for t in (tests_data.get("tests") or [])
        ]

        return jsonify({
            "produto_id": produto_id,
            "produto_nome": produto_config[produto_id]["nome"],
            "testes": testes,
            "total": len(testes)
        })
    
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao obter testes disponíveis: {exc}"}), 500


@app.get("/api/client/progress-produto")
def get_client_progress_with_product():
    """Consulta progresso do CNPJ considerando o produto selecionado."""
    try:
        result = get_client_progress_payload_for_product(
            cnpj=str(request.args.get("cnpj") or "").strip(),
            produto_id=str(request.args.get("produto_id") or "01").strip().zfill(2),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao consultar progresso do cliente: {exc}"}), 500

    return jsonify(result)


@app.get("/api/client/progress-all-products")
def get_client_progress_all_products_route():
    """Consulta progresso do CNPJ em todos os produtos (QR + Autorizador)."""
    try:
        result = get_client_progress_payload_all_products(
            cnpj=str(request.args.get("cnpj") or "").strip(),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao consultar progresso do cliente por produto: {exc}"}), 500

    return jsonify(result)


@app.get("/api/admin/clients-produtos")
def admin_list_clients_products():
    try:
        return jsonify(list_clients_payload_multiproduct())
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao listar clientes por produto: {exc}"}), 500


@app.post("/api/admin/clients/<path:cnpj>/tests-produto")
def admin_set_tests_product(cnpj: str):
    try:
        raw = request.get_json(silent=True) or {}
        selected_tests = list(raw.get("selected_tests") or request.form.getlist("selected_tests") or [])
        produto_id = str(raw.get("produto_id") or request.form.get("produto_id") or "01").strip().zfill(2)
        result = admin_set_client_tests_for_product(cnpj=cnpj, produto_id=produto_id, selected_test_ids=selected_tests)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao atualizar testes do cliente por produto: {exc}"}), 500
    return jsonify(result)


@app.post("/api/admin/clients/<path:cnpj>/reset-onboarding-produto")
def admin_reset_onboarding_product(cnpj: str):
    try:
        raw = request.get_json(silent=True) or {}
        produto_id = str(raw.get("produto_id") or request.form.get("produto_id") or "01").strip().zfill(2)
        result = admin_reset_client_onboarding_for_product(cnpj=cnpj, produto_id=produto_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao resetar onboarding por produto: {exc}"}), 500
    return jsonify(result)


@app.post("/api/admin/clients/<path:cnpj>/reset-tests-produto")
def admin_reset_tests_product(cnpj: str):
    try:
        raw = request.get_json(silent=True) or {}
        produto_id = str(raw.get("produto_id") or request.form.get("produto_id") or "01").strip().zfill(2)
        result = admin_reset_client_tests_for_product(cnpj=cnpj, produto_id=produto_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao resetar testes por produto: {exc}"}), 500
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
