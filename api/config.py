"""
api/config.py
Classes de configuração Flask por ambiente.
"""

import os


class BaseConfig:
    SECRET_KEY: str = os.getenv(
        "FLASK_SECRET_KEY", "dev-secret-change-in-prod"
    )
    API_TOKEN_HEADER: str = "X-API-Token"

    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL", "sqlite:///sentinelnet.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    AUDIT_LOG_DIR: str = os.getenv(
        "AUDIT_LOG_DIR", "logs/"
    )

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
