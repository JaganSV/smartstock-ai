"""Request-ID and request-size middleware (pure ASGI so they work with exception handlers)."""

import re
import uuid
from collections.abc import Mapping

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import envelope_response
from app.core.logging import request_id_ctx

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{1,64}")


class RequestIdMiddleware:
    """Accept a valid incoming X-Request-ID or generate a UUID4; echo it on the response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
        request_id = (
            incoming if incoming and _VALID_REQUEST_ID.fullmatch(incoming) else str(uuid.uuid4())
        )
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_ctx.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_ctx.reset(token)


class RequestSizeLimitMiddleware:
    """Reject a request whose ``Content-Length`` exceeds the limit with 413 (BP 10.3).

    ``path_limits`` maps an exact path to its own limit (for example a later upload route), so
    one route can allow more than the default without raising it everywhere. A request without a
    ``Content-Length`` header is not rejected here.
    """

    def __init__(
        self, app: ASGIApp, max_bytes: int, path_limits: Mapping[str, int] | None = None
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.path_limits = dict(path_limits or {})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.path_limits.get(scope["path"], self.max_bytes)
        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            request_id = scope.get("state", {}).get("request_id")
            if not declared.isdigit():
                response = envelope_response(
                    request_id, 400, "BAD_REQUEST", "Invalid Content-Length"
                )
                await response(scope, receive, send)
                return
            if int(declared) > limit:
                response = envelope_response(
                    request_id, 413, "VALIDATION_ERROR", "Request body too large"
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
