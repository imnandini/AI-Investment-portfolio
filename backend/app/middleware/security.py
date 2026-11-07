"""Request limits and privacy-safe logs. No bodies, query strings or tokens."""
from collections import OrderedDict, deque
import asyncio
import hashlib
import logging
import time
from uuid import uuid4
from starlette.responses import JSONResponse

logger = logging.getLogger("copilot.requests")


class SecurityMiddleware:
    def __init__(self, app, limit=120):
        self.app = app
        self.limit = limit
        self.requests = OrderedDict()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        # Per connection IP. Do not trust spoofable forwarded headers or token strings.
        key = hashlib.sha256(str(scope.get("client", ("unknown",))[0]).encode()).digest()
        now = time.monotonic()
        bucket = self.requests.setdefault(key, deque())
        self.requests.move_to_end(key)
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        while len(self.requests) > 10000:
            self.requests.popitem(last=False)
        if scope["path"] != "/health":
            if len(bucket) >= self.limit:
                return await JSONResponse({"detail": "Request limit reached. Try again in one minute."}, status_code=429, headers={"Retry-After": "60"})(scope, receive, send)
            bucket.append(now)
        length = headers.get(b"content-length", b"0")
        try:
            oversized = int(length) > 6 * 1024 * 1024
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length."}, 400)(scope, receive, send)
        if oversized:
            return await JSONResponse({"detail": "Request exceeds 6 MB."}, 413)(scope, receive, send)
        if scope["method"] in {"POST", "PUT", "PATCH"}:
            parts = []
            byte_count = 0
            try:
                while True:
                    event = await asyncio.wait_for(receive(), timeout=15)
                    if event["type"] == "http.disconnect":
                        return
                    part = event.get("body", b"")
                    byte_count += len(part)
                    if byte_count > 6 * 1024 * 1024:
                        return await JSONResponse({"detail": "Request exceeds 6 MB."}, 413)(scope, receive, send)
                    parts.append(part)
                    if not event.get("more_body", False):
                        break
            except asyncio.TimeoutError:
                return await JSONResponse({"detail": "Upload timed out."}, 408)(scope, receive, send)
            buffered = b"".join(parts)
            delivered = False
            original_receive = receive

            async def replay():
                nonlocal delivered
                if delivered:
                    return await original_receive()
                delivered = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            receive = replay
        request_id = str(uuid4())
        status = 500

        async def safe_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-request-id", request_id.encode()), (b"x-content-type-options", b"nosniff"),
                    (b"cache-control", b"no-store"), (b"referrer-policy", b"no-referrer")]
            await send(message)
        try:
            await self.app(scope, receive, safe_send)
        except Exception as exc:
            logger.error("request_id=%s error_type=%s", request_id, type(exc).__name__)
            await JSONResponse({"detail": "The request could not finish. Retry or check the service configuration.", "request_id": request_id}, 500)(scope, receive, safe_send)
        finally:
            route = scope.get("route")
            logger.info("request_id=%s method=%s route=%s status=%s elapsed_ms=%.1f", request_id, scope["method"], getattr(route, "path", "unmatched"), status, (time.monotonic()-now)*1000)
