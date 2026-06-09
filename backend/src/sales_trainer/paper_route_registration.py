from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter

RouteHandler = Callable[..., Coroutine[Any, Any, Any]]


def add_paper_admin_routes(
    router: APIRouter,
    *,
    list_handler: RouteHandler,
    create_handler: RouteHandler,
    update_handler: RouteHandler,
    revisions_handler: RouteHandler,
    publish_handler: RouteHandler,
    archive_handler: RouteHandler,
    rollback_handler: RouteHandler,
) -> None:
    _add(router, "/papers", list_handler, "GET")
    _add(router, "/papers", create_handler, "POST")
    _add(router, "/papers/{paper_id}", update_handler, "PUT")
    _add(router, "/papers/{paper_id}/revisions", revisions_handler, "GET")
    _add(router, "/papers/{paper_id}/publish", publish_handler, "POST")
    _add(router, "/papers/{paper_id}/rollback", rollback_handler, "POST")
    _add(router, "/papers/{paper_id}/archive", archive_handler, "POST")


def add_paper_learner_routes(
    router: APIRouter,
    *,
    get_handler: RouteHandler,
    submit_handler: RouteHandler,
) -> None:
    _add(router, "/papers/{paper_id}", get_handler, "GET")
    _add(router, "/paper-attempts", submit_handler, "POST")


def _add(router: APIRouter, path: str, handler: RouteHandler, method: str) -> None:
    router.add_api_route(path, handler, methods=[method], response_model=None)
