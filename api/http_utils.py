"""
api/http_utils.py
Utilitários HTTP exclusivos da camada web Flask.
"""

from __future__ import annotations

from flask import Request


def wants_json(request: Request) -> bool:
    """True se o cliente prefere application/json."""
    best = request.accept_mimetypes.best_match(
        ["application/json", "text/html"]
    )
    return best == "application/json"
