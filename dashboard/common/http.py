from __future__ import annotations

from flask import Request


def wants_json(request: Request) -> bool:
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json"
