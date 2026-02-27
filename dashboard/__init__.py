"""
dashboard/__init__.py
App Factory do SentinelNet Dashboard (Flask).

Uso:
    from dashboard import create_app
    app = create_app()
"""

from flask import Flask, redirect, url_for

from .config import DevelopmentConfig
from .blueprints.auth import auth_bp
from .blueprints.health import health_bp
from .blueprints.devices import devices_bp
from .blueprints.incidents import incidents_bp
from .blueprints.remediation import remediation_bp
from .blueprints.admin import admin_bp


def create_app(config_class=DevelopmentConfig) -> Flask:
    """Cria e configura a instância Flask (App Factory Pattern)."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    app.config.from_object(config_class)

    # ── Registrar Blueprints ──────────────────────────────────────────────────
    app.register_blueprint(auth_bp,        url_prefix="/auth")
    app.register_blueprint(health_bp,      url_prefix="/health")
    app.register_blueprint(devices_bp,     url_prefix="/devices")
    app.register_blueprint(incidents_bp,   url_prefix="/incidents")
    app.register_blueprint(remediation_bp, url_prefix="/incidents")
    app.register_blueprint(admin_bp,       url_prefix="/admin")

    # ── Rota raiz ─────────────────────────────────────────────────────────────
    @app.get("/")
    def index():
        return redirect(url_for("health.overview"))

    return app
