"""
api/blueprints/auth.py
Blueprint de autenticação por token (Bearer / X-API-Token).

- Expõe o decorator `token_required` para proteger rotas.
- Rota /auth/verify permite testar o token sem efeitos
  colaterais.
"""

from functools import wraps

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
)

auth_bp = Blueprint("auth", __name__)


def token_required(f):
    """Decorator: exige X-API-Token válido no header."""

    @wraps(f)
    def decorated(*args, **kwargs):
        header = current_app.config.get(
            "API_TOKEN_HEADER", "X-API-Token"
        )
        token = request.headers.get(header)

        if not token:
            return (
                jsonify(
                    {
                        "error": (
                            "Token de autenticação "
                            "ausente."
                        )
                    }
                ),
                401,
            )

        valid_token = current_app.config.get(
            "API_STATIC_TOKEN"
        )
        if valid_token and token != valid_token:
            return (
                jsonify(
                    {
                        "error": (
                            "Token inválido ou "
                            "expirado."
                        )
                    }
                ),
                403,
            )

        return f(*args, **kwargs)

    return decorated


# ── Rotas ─────────────────────────────────────────────


@auth_bp.get("/verify")
@token_required
def verify():
    """Verifica se o token fornecido é válido."""
    return jsonify(
        {"status": "ok", "message": "Token válido."}
    )
