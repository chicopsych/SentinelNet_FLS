"""
run.py — Ponto de entrada de desenvolvimento do SentinelNet Dashboard.

Uso:
    python run.py                      # modo desenvolvimento (padrão)
    FLASK_ENV=production python run.py # modo produção
"""

import os

from dashboard import create_app
from dashboard.config import DevelopmentConfig, ProductionConfig

_ENV_MAP = {
    "production": ProductionConfig,
    "prod":       ProductionConfig,
}

env = os.getenv("FLASK_ENV", "development").lower()
config_class = _ENV_MAP.get(env, DevelopmentConfig)

app = create_app(config_class=config_class)

debug_mode = bool(app.config.get("DEBUG", False))
if env in _ENV_MAP:
    debug_mode = False

if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", 5000)),
        debug=debug_mode,
    )
