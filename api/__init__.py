"""
api/__init__.py
App Factory do SentinelNet Dashboard (Flask).

Uso:
    from api import create_app
    app = create_app()
"""

from flask import Flask, redirect, url_for

from api.blueprints.admin import admin_bp
from api.blueprints.auth import auth_bp
from api.blueprints.devices import devices_bp
from api.blueprints.health import health_bp
from api.blueprints.incidents import incidents_bp
from api.blueprints.remediation import remediation_bp
from api.blueprints.topology import topology_bp
from api.config import DevelopmentConfig


def create_app(config_class=DevelopmentConfig) -> Flask:
    """Cria e configura a instância Flask."""

    app = Flask(
        __name__,
        template_folder="../dashboard/templates",
        static_folder="../dashboard/static",
    )

    app.config.from_object(config_class)

    # ── Blueprints ────────────────────────────────────
    app.register_blueprint(
        auth_bp, url_prefix="/auth"
    )
    app.register_blueprint(
        health_bp, url_prefix="/health"
    )
    app.register_blueprint(
        devices_bp, url_prefix="/devices"
    )
    app.register_blueprint(
        incidents_bp, url_prefix="/incidents"
    )
    app.register_blueprint(
        remediation_bp, url_prefix="/incidents"
    )
    app.register_blueprint(
        admin_bp, url_prefix="/admin"
    )
    app.register_blueprint(
        topology_bp, url_prefix="/topology"
    )

    # ── Rota raiz ─────────────────────────────────────
    @app.get("/")
    def index():
        return redirect(url_for("health.overview"))

    return app
