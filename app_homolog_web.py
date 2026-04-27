from __future__ import annotations

import importlib.util
from pathlib import Path

from flask import Flask, jsonify, render_template, request

APP_DIR = Path(__file__).resolve().parent
SERVICE_PATH = APP_DIR / "homolog_service.py"
SERVICE_SPEC = importlib.util.spec_from_file_location("homolog_service", SERVICE_PATH)
if SERVICE_SPEC is None or SERVICE_SPEC.loader is None:
    raise RuntimeError(f"Não foi possível carregar o serviço da API em {SERVICE_PATH}")

homolog_service = importlib.util.module_from_spec(SERVICE_SPEC)
SERVICE_SPEC.loader.exec_module(homolog_service)

BASE_DIR = homolog_service.BASE_DIR
get_api_config_payload = homolog_service.get_api_config_payload
get_health_payload = homolog_service.get_health_payload
get_log_summary_payload = homolog_service.get_log_summary_payload
get_tests_payload = homolog_service.get_tests_payload
list_logs_payload = homolog_service.list_logs_payload
validate_log_payload = homolog_service.validate_log_payload

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)


@app.get("/")
def home():
    return render_template("index.html")


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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
