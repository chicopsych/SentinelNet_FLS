"""
dashboard/config.py
Classes de configuração Flask por ambiente.

A classe ativa é selecionada ao chamar create_app(config_class=...).
"""

import os


class BaseConfig:
    # ── Segurança ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-prod")
    API_TOKEN_HEADER: str = "X-API-Token"

    # ── Banco de Dados ────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL", "sqlite:///sentinelnet.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # ── Auditoria / Logs ──────────────────────────────────────────────────────
    AUDIT_LOG_DIR: str = os.getenv("AUDIT_LOG_DIR", "logs/")

    # ── Paginação padrão da API ───────────────────────────────────────────────
    PAGE_SIZE: int = 25


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True
    TESTING: bool = False


class ProductionConfig(BaseConfig):
    DEBUG: bool = False
    TESTING: bool = False


class TestingConfig(BaseConfig):
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
