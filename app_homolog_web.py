from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, url_for

APP_DIR = Path(__file__).resolve().parent
SERVICE_PATH = APP_DIR / "homolog_service.py"
SERVICE_SPEC = importlib.util.spec_from_file_location("homolog_service", SERVICE_PATH)
if SERVICE_SPEC is None or SERVICE_SPEC.loader is None:
    raise RuntimeError(f"Não foi possível carregar o serviço da API em {SERVICE_PATH}")

homolog_service = importlib.util.module_from_spec(SERVICE_SPEC)
SERVICE_SPEC.loader.exec_module(homolog_service)

BASE_DIR = homolog_service.BASE_DIR
get_api_config_payload = homolog_service.get_api_config_payload
admin_reset_client_onboarding = homolog_service.admin_reset_client_onboarding
admin_reset_client_tests = homolog_service.admin_reset_client_tests
admin_set_client_tests = homolog_service.admin_set_client_tests
enroll_client_tests = homolog_service.enroll_client_tests
get_health_payload = homolog_service.get_health_payload
get_client_progress_payload = homolog_service.get_client_progress_payload
get_log_summary_payload = homolog_service.get_log_summary_payload
get_tests_payload = homolog_service.get_tests_payload
list_clients_payload = homolog_service.list_clients_payload
list_logs_payload = homolog_service.list_logs_payload
validate_client_payload = homolog_service.validate_client_payload
validate_log_payload = homolog_service.validate_log_payload

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.config["SECRET_KEY"] = os.environ.get("HOMOLOG_SECRET_KEY", "homolog-stage2-local-secret")


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


@app.get("/api/health")
def get_health():
    return jsonify(get_health_payload())


@app.get("/api/config")
def get_config():
    return jsonify(get_api_config_payload())


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


@app.post("/api/client/validate")
def validate_client():
    try:
        result = validate_client_payload(
            cnpj=str(request.form.get("cnpj") or "").strip(),
            data_teste=str(request.form.get("data_teste") or "").strip(),
            teste_id=str(request.form.get("teste_id") or "").strip(),
            de11=str(request.form.get("de11") or "").strip(),
            de41=str(request.form.get("de41") or "").strip(),
        )
    except ValueError as exc:
        status = 413 if "excede o limite" in str(exc) else 400
        return jsonify({"error": str(exc)}), status
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao processar homologação do cliente: {exc}"}), 500

    return jsonify(result)


@app.post("/api/client/enroll")
def enroll_client():
    try:
        selected_tests = request.form.getlist("selected_tests")
        if not selected_tests:
            raw_selected = request.get_json(silent=True) or {}
            selected_tests = list(raw_selected.get("selected_tests") or [])

        result = enroll_client_tests(
            cnpj=str(request.form.get("cnpj") or (request.get_json(silent=True) or {}).get("cnpj") or "").strip(),
            selected_test_ids=selected_tests,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao registrar testes do cliente: {exc}"}), 500

    return jsonify(result)


@app.get("/api/client/progress")
def get_client_progress():
    try:
        result = get_client_progress_payload(
            cnpj=str(request.args.get("cnpj") or "").strip(),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao consultar progresso do cliente: {exc}"}), 500

    return jsonify(result)


@app.get("/api/admin/clients")
def admin_list_clients():
    try:
        return jsonify(list_clients_payload())
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao listar clientes: {exc}"}), 500


@app.post("/api/admin/clients/<path:cnpj>/tests")
def admin_set_tests(cnpj: str):
    try:
        raw = request.get_json(silent=True) or {}
        selected_tests = list(raw.get("selected_tests") or request.form.getlist("selected_tests") or [])
        result = admin_set_client_tests(cnpj=cnpj, selected_test_ids=selected_tests)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao atualizar testes do cliente: {exc}"}), 500
    return jsonify(result)


@app.post("/api/admin/clients/<path:cnpj>/reset-onboarding")
def admin_reset_onboarding(cnpj: str):
    try:
        result = admin_reset_client_onboarding(cnpj=cnpj)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao resetar onboarding: {exc}"}), 500
    return jsonify(result)


@app.post("/api/admin/clients/<path:cnpj>/reset-tests")
def admin_reset_tests(cnpj: str):
    try:
        result = admin_reset_client_tests(cnpj=cnpj)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Falha ao resetar testes: {exc}"}), 500
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
