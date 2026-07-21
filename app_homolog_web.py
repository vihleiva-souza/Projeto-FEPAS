from __future__ import annotations

import os
from functools import wraps

from flask import Flask, jsonify, render_template, request, url_for, session, redirect

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

# Configurar chave secreta para sessões
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
app.config["SECRET_KEY"] = os.environ.get("HOMOLOG_SECRET_KEY", "homolog-stage2-local-secret")

# Configurações de sessão
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = 86400  # 24 horas
app.config["SESSION_COOKIE_SECURE"] = True  # HTTPS only
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

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
    """Painel interno protegido por autenticação."""
    if not session.get("authenticated"):
        return redirect("/admin/painel-login")
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


@app.get("/admin/painel-login")
def admin_painel_login():
    """Página de login para acessar o painel interno."""
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - Painel Interno</title>
        <style>
            :root {
              --bg: #eef3fa;
              --ink: #10243d;
              --muted: #4a5f7d;
              --panel: rgba(248, 251, 255, 0.9);
              --line: #bcd0ea;
              --ok: #0f6e4f;
              --bad: #c13232;
              --na: #4a5f77;
              --accent: #f26a21;
              --brand-blue: #0057b8;
            }
            
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Space Grotesk', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: 
                    linear-gradient(120deg, rgba(8, 33, 66, 0.66), rgba(8, 56, 108, 0.52)),
                    radial-gradient(circle at 16% 20%, rgba(242, 106, 33, 0.58), transparent 44%),
                    radial-gradient(circle at 82% 88%, rgba(255, 132, 48, 0.34), transparent 38%),
                    url('/static/Fiserv_Teams_Backgrounds_V5.jpg') center center / cover no-repeat fixed;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
                color: var(--ink);
                position: relative;
                overflow-x: hidden;
            }
            body::before {
                content: '';
                position: fixed;
                width: 360px;
                height: 360px;
                background: #ff7c2c;
                border-radius: 999px;
                filter: blur(60px);
                opacity: 0.34;
                top: -120px;
                left: -100px;
                pointer-events: none;
            }
            body::after {
                content: '';
                position: fixed;
                width: 340px;
                height: 340px;
                background: #ff9a2c;
                border-radius: 999px;
                filter: blur(60px);
                opacity: 0.24;
                bottom: -80px;
                right: -60px;
                pointer-events: none;
            }
            .login-container {
                background: var(--panel);
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
                width: 100%;
                max-width: 400px;
                padding: 40px;
                border: 1px solid var(--line);
                position: relative;
                z-index: 10;
            }
            .login-header {
                text-align: center;
                margin-bottom: 30px;
            }
            .login-header h1 {
                font-size: 24px;
                color: #f26a21;
                margin-bottom: 10px;
            }
            .login-header p {
                color: #ff9a52;
                font-size: 14px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            .form-group label {
                display: block;
                margin-bottom: 8px;
                color: #f26a21;
                font-weight: bold;
                font-size: 14px;
            }
            .form-group input {
                width: 100%;
                padding: 12px;
                border: 1px solid var(--line);
                border-radius: 5px;
                font-size: 14px;
                transition: border-color 0.2s;
                background: white;
                color: var(--ink);
            }
            .form-group input:focus {
                outline: none;
                border-color: #f26a21;
                box-shadow: 0 0 0 2px rgba(242, 106, 33, 0.1);
            }
            .btn-login {
                width: 100%;
                padding: 12px;
                background: var(--brand-blue);
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.2s;
            }
            .btn-login:hover {
                transform: scale(1.02);
                background: #0066d9;
            }
            .btn-login:disabled {
                opacity: 0.7;
                cursor: not-allowed;
            }
            .error-message {
                background: rgba(242, 106, 33, 0.1);
                border: 1px solid #f26a21;
                padding: 12px;
                border-radius: 5px;
                color: #f26a21;
                margin-bottom: 20px;
                display: none;
                font-size: 14px;
            }
            .loading {
                display: none;
                text-align: center;
                color: #f26a21;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="login-header">
                <h1>🔐 Painel Interno</h1>
                <p>Acesso exclusivo para equipe interna</p>
            </div>
            
            <div id="errorMessage" class="error-message"></div>
            
            <form id="loginForm">
                <div class="form-group">
                    <label for="password">Senha:</label>
                    <input type="password" id="password" name="password" placeholder="Digite a senha" required>
                </div>
                
                <button type="submit" class="btn-login" id="submitBtn">Acessar Painel</button>
                <div class="loading" id="loading">Verificando credenciais...</div>
            </form>
        </div>

        <script>
            const form = document.getElementById('loginForm');
            const submitBtn = document.getElementById('submitBtn');
            const loading = document.getElementById('loading');
            const errorMessage = document.getElementById('errorMessage');
            
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                submitBtn.style.display = 'none';
                loading.style.display = 'block';
                errorMessage.style.display = 'none';
                
                const password = document.getElementById('password').value;
                
                try {
                    const response = await fetch('/api/admin/painel-auth', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok && data.success) {
                        window.location.href = '/interno';
                    } else {
                        throw new Error(data.error || 'Erro ao fazer login');
                    }
                } catch (error) {
                    errorMessage.textContent = '❌ ' + error.message;
                    errorMessage.style.display = 'block';
                    submitBtn.style.display = 'block';
                    loading.style.display = 'none';
                }
            });
        </script>
    </body>
    </html>
    """


@app.post("/api/admin/painel-auth")
def admin_painel_auth():
    """Valida senha do painel interno e cria sessão."""
    try:
        data = request.get_json(silent=True) or {}
        password = str(data.get("password") or "").strip()
        
        if not password:
            return jsonify({"success": False, "error": "Senha é obrigatória"}), 400
        
        admin_password = os.environ.get("PAINEL_ADMIN_PASSWORD", "")
        if not admin_password:
            return jsonify({"success": False, "error": "Sistema não configurado"}), 500
        
        if password != admin_password:
            return jsonify({"success": False, "error": "Senha incorreta"}), 401
        
        # Cria sessão
        session["authenticated"] = True
        session.permanent = True
        
        return jsonify({"success": True, "message": "Autenticado com sucesso"})
    
    except Exception as exc:
        return jsonify({"success": False, "error": f"Erro: {exc}"}), 500



def admin_painel_logout():
    """Faz logout e limpa a sessão."""
    session.clear()
    if request.method == "GET":
        return redirect("/admin/painel-login")
    return jsonify({"success": True, "message": "Desconectado com sucesso"})


@app.get("/admin/roteiros-dashboard")
def admin_roteiros_dashboard():
    """Dashboard visual para gerenciar roteiros. Protegido por autenticação de sessão."""
    if not session.get("authenticated"):
        return redirect("/admin/painel-login")
    
    if not db_store.is_enabled():
        return "Banco de dados não configurado", 503
    
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard de Roteiros</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .header-content {
                text-align: center;
                flex: 1;
            }
            .header h1 { font-size: 28px; margin-bottom: 5px; }
            .header p { font-size: 14px; opacity: 0.9; }
            .btn-logout {
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border: 1px solid white;
                padding: 8px 15px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 12px;
                transition: background 0.2s;
            }
            .btn-logout:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            .content { padding: 30px; }
            .loading { text-align: center; padding: 40px; color: #666; }
            .error { 
                background: #fee; 
                border: 1px solid #fcc; 
                padding: 15px; 
                border-radius: 5px; 
                color: #c33;
                margin-bottom: 20px;
            }
            .success {
                background: #efe;
                border: 1px solid #cfc;
                padding: 15px;
                border-radius: 5px;
                color: #3c3;
                margin-bottom: 20px;
            }
            .cards-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                gap: 20px;
            }
            .card {
                border: 1px solid #eee;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                transition: transform 0.2s, box-shadow 0.2s;
            }
            .card:hover {
                transform: translateY(-5px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.15);
            }
            .card-header {
                background: #f5f5f5;
                padding: 15px;
                border-bottom: 2px solid #667eea;
            }
            .card-header h3 {
                font-size: 16px;
                color: #333;
                word-break: break-word;
            }
            .card-body {
                padding: 15px;
            }
            .info-row {
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
                font-size: 14px;
            }
            .info-label { font-weight: bold; color: #666; }
            .info-value { color: #333; text-align: right; }
            .badge {
                display: inline-block;
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
                margin-top: 10px;
            }
            .badge-produto { background: #e3f2fd; color: #1976d2; }
            .badge-cnpj { background: #f3e5f5; color: #7b1fa2; }
            .card-footer {
                padding: 15px;
                background: #fafafa;
                border-top: 1px solid #eee;
                text-align: center;
            }
            .btn {
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
                font-weight: bold;
                transition: background 0.2s;
            }
            .btn-download {
                background: #667eea;
                color: white;
            }
            .btn-download:hover { background: #764ba2; }
            .empty {
                text-align: center;
                padding: 60px 20px;
                color: #999;
            }
            .empty-icon { font-size: 48px; margin-bottom: 15px; }
            .date { font-size: 12px; color: #999; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-content">
                    <h1>📋 Dashboard de Roteiros</h1>
                    <p>Gerenciador de submissões de roteiros do cliente</p>
                </div>
                <button id="logoutBtn" class="btn-logout">🚪 Sair</button>
            </div>
            <div class="content">
                <div id="message"></div>
                <div id="loading" class="loading">Carregando roteiros...</div>
                <div id="roteiros" style="display:none;"></div>
            </div>
        </div>

        <script>
            document.getElementById('logoutBtn').addEventListener('click', async () => {
                const response = await fetch('/api/admin/painel-logout', { method: 'POST' });
                if (response.ok) {
                    window.location.href = '/admin/painel-login';
                }
            });
            
            async function carregarRoteiros() {
                try {
                    const response = await fetch(`/api/admin/roteiros`);
                    if (!response.ok) {
                        if (response.status === 401) {
                            window.location.href = '/admin/painel-login';
                        }
                        throw new Error('Erro ao carregar roteiros');
                    }
                    
                    const data = await response.json();
                    document.getElementById('loading').style.display = 'none';
                    
                    if (data.total === 0) {
                        document.getElementById('roteiros').innerHTML = `
                            <div class="empty">
                                <div class="empty-icon">📭</div>
                                <h3>Nenhum roteiro encontrado</h3>
                                <p>Aguardando submissões dos clientes...</p>
                            </div>
                        `;
                    } else {
                        let html = '<div class="cards-grid">';
                        data.submissoes.forEach(sub => {
                            const data_formatada = new Date(sub.created_at).toLocaleDateString('pt-BR', {
                                year: 'numeric', month: '2-digit', day: '2-digit', 
                                hour: '2-digit', minute: '2-digit'
                            });
                            html += `
                                <div class="card">
                                    <div class="card-header">
                                        <h3>📄 ${sub.roteiro_filename}</h3>
                                    </div>
                                    <div class="card-body">
                                        <div class="info-row">
                                            <span class="info-label">CNPJ:</span>
                                            <span class="info-value"><strong>${sub.cnpj}</strong></span>
                                        </div>
                                        <div class="info-row">
                                            <span class="info-label">Produto:</span>
                                            <span class="info-value">${sub.produto_id}</span>
                                        </div>
                                        <div class="info-row">
                                            <span class="info-label">Log:</span>
                                            <span class="info-value">${sub.log_name}</span>
                                        </div>
                                        <div class="badge badge-produto">Produto: ${sub.produto_id}</div>
                                        <div class="badge badge-cnpj">CNPJ: ${sub.cnpj}</div>
                                        <div class="date">📅 ${data_formatada}</div>
                                    </div>
                                    <div class="card-footer">
                                        <a href="/api/admin/roteiros/download/${sub.submissao_id}" 
                                           download class="btn btn-download">
                                            ⬇️ Baixar Roteiro
                                        </a>
                                    </div>
                                </div>
                            `;
                        });
                        html += '</div>';
                        document.getElementById('roteiros').innerHTML = html;
                    }
                    document.getElementById('roteiros').style.display = 'block';
                } catch (error) {
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('message').innerHTML = `<div class="error">❌ Erro: ${error.message}</div>`;
                }
            }
            
            carregarRoteiros();
        </script>
    </body>
    </html>
    """


@app.get("/api/admin/roteiros")
def admin_list_roteiros():
    """Lista todas as submissões de roteiro salvas no banco. Protegido por autenticação de sessão."""
    if not session.get("authenticated"):
        return jsonify({"error": "Não autorizado"}), 401
    if not db_store.is_enabled():
        return jsonify({"error": "Banco de dados não configurado"}), 503
    submissoes = db_store.list_roteiro_submissions()
    return jsonify({"total": len(submissoes), "submissoes": submissoes})


@app.get("/api/admin/roteiros/download/<submissao_id>")
def admin_download_roteiro(submissao_id: str):
    """Faz download do arquivo .docx original enviado pelo cliente. Protegido por autenticação de sessão."""
    from flask import Response
    if not session.get("authenticated"):
        return jsonify({"error": "Não autorizado"}), 401
    if not db_store.is_enabled():
        return jsonify({"error": "Banco de dados não configurado"}), 503
    result = db_store.get_roteiro_content(submissao_id)
    if result is None:
        return jsonify({"error": "Submissão não encontrada"}), 404
    filename, content = result
    safe_filename = filename if filename.lower().endswith(".docx") else filename + ".docx"
    return Response(
        content,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
