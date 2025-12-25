from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from typing import Callable
import time
import uuid
import fnmatch
from sqlalchemy import select

from app.config.settings import settings
from app.utils.logging import get_logger
from app.utils.request_utils import get_request_origin
from app.common.enums import Environment
from app.cache.keys import CacheKeys

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log request details and processing time.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler
            
        Returns:
            HTTP response
        """
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        start_time = time.time()
        logger.info(
            f"Request started | ID: {request_id} | "
            f"Method: {request.method} | Path: {request.url.path}"
        )
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"
            
            logger.info(
                f"Request completed | ID: {request_id} | "
                f"Status: {response.status_code} | "
                f"Time: {process_time:.4f}s"
            )
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed | ID: {request_id} | "
                f"Error: {str(e)} | Time: {process_time:.4f}s",
                exc_info=True
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting based on IP address.
    Uses Redis for distributed rate limiting.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check rate limit before processing request.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler
            
        Returns:
            HTTP response or 429 if rate limit exceeded
        """
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        
        redis = request.app.state.redis if hasattr(request.app.state, "redis") else None
        
        if redis:
            try:
                rate_key = CacheKeys.rate_limit_ip(client_ip)
                
                current = await redis.get(rate_key)
                
                if current and int(current) >= settings.RATE_LIMIT_IP_PER_MINUTE:
                    logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "detail": "Rate limit exceeded. Please try again later.",
                            "retry_after": 60
                        },
                        headers={"Retry-After": "60"}
                    )
                
                pipe = redis.pipeline()
                pipe.incr(rate_key)
                pipe.expire(rate_key, 60)  
                await pipe.execute()
                
            except Exception as e:
                logger.error(f"Rate limit check failed: {str(e)}")
        
        return await call_next(request)


class WidgetCORSMiddleware(BaseHTTPMiddleware):
    """
    Middleware for validating widget CORS origins against allowed_origins table.
    Supports wildcard patterns (e.g., https://*.example.com).
    Uses cache-aside pattern: Cache -> DB -> Cache.
    Can be bypassed in development mode with SKIP_ORIGIN_CHECK=true.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Validate origin against allowed origins with cache.
        
        Flow:
        1. Get origin from request header
        2. Check if dev mode bypass is enabled
        3. Check cache for allowed origins by bot_key
        4. If cache miss, query DB and cache result
        5. Validate origin against patterns (including wildcards)
        6. Add CORS headers if valid
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler
            
        Returns:
            HTTP response with CORS headers if valid
        """
        path = request.url.path
        if path.startswith("/api/v1/widget") or path.startswith("/api/v1/chat"):
            
            if path.startswith("/api/v1/widget/js"):
                response = await call_next(request)
                response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type"
                return response
            
            if request.method == "OPTIONS":
                origin = get_request_origin(request) or "*"
                return Response(
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Bot-Key",
                        "Access-Control-Max-Age": "86400",
                    }
                )
            
            session_based_paths = [
                "/api/v1/widget/chat",
                "/api/v1/widget/init",
                "/api/v1/chat/stream/",
                "/api/v1/chat/task/",
            ]
            if any(path.startswith(sp) for sp in session_based_paths):
                response = await call_next(request)
                origin = get_request_origin(request) or "*"
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type"
                return response
            
            if settings.SKIP_ORIGIN_CHECK and settings.ENV == Environment.DEVELOPMENT.value:
                response = await call_next(request)
                
                origin = get_request_origin(request) or "*"
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                
                return response
            
            origin = get_request_origin(request)
            if not origin or origin.startswith(("http://localhost", "http://127.0.0.1")):
                if settings.ENV == Environment.DEVELOPMENT.value:
                    return await call_next(request)
            
            bot_key = request.query_params.get("bot_key") or request.path_params.get("bot_key")
            bot_id = None
            
            import re
            bot_id_match = re.search(r'/widget/config/([a-f0-9-]{36})', path)
            if bot_id_match:
                bot_id = bot_id_match.group(1)
            
            if not bot_id and '/chat' in path and request.method == "POST":
                try:
                    body = await request.body()
                    if body:
                        import json
                        payload = json.loads(body)
                        bot_id = payload.get("bot_id")
                        async def receive():
                            return {"type": "http.request", "body": body}
                        request._receive = receive
                except Exception as e:
                    logger.error(f"Failed to parse request body: {e}")
            
            if not bot_key and not bot_id:
                logger.warning(f"Request without bot_key/bot_id from origin: {origin}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "bot_key or bot_id is required"}
                )
            
            is_allowed = await self._is_origin_allowed(request, bot_key, bot_id, origin)
            
            if not is_allowed:
                bot_identifier = bot_key or bot_id
                logger.warning(f"Request from unauthorized origin: {origin} for bot: {bot_identifier}")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Origin not allowed for this bot"}
                )
            
            response = await call_next(request)
            
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            
            return response
        
        else:
            origin = get_request_origin(request) or "*"
            
            if request.method == "OPTIONS":
                return Response(
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Request-ID",
                        "Access-Control-Max-Age": "86400",
                    }
                )
            
            response = await call_next(request)
            
            if origin:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID"
            
            return response
    
    async def _is_origin_allowed(
        self, 
        request: Request, 
        bot_key: str | None, 
        bot_id: str | None, 
        origin: str
    ) -> bool:
        """
        Check if origin is allowed for bot using cache-aside pattern.
        
        Flow:
        1. Check global CORS_ORIGINS first (localhost, widget server, admin panel)
        2. If not in global list, check per-bot allowed_origins from DB
        
        Args:
            request: FastAPI request (to access app state)
            bot_key: Bot key identifier (for widget endpoints)
            bot_id: Bot ID (for chat endpoints)
            origin: Request origin to validate
            
        Returns:
            True if origin is allowed
        """
        if self._match_origin_patterns(origin, settings.CORS_ORIGINS):
            return True
        
        redis = request.app.state.redis if hasattr(request.app.state, "redis") else None
        
        cache_identifier = bot_key or bot_id
        cache_key = CacheKeys.allowed_origins(cache_identifier)
        
        if redis:
            try:
                cached_origins = await redis.smembers(cache_key)
                if cached_origins:
                    return self._match_origin_patterns(origin, cached_origins)
            except Exception as e:
                logger.error(f"Failed to check cache for allowed origins: {e}")
        
        db = request.app.state.db_session if hasattr(request.app.state, "db_session") else None
        if not db:
            logger.error("Database session not available in app state")
            return False
        
        try:
            from app.models.bot import AllowedOrigin, Bot
            
            async with db() as session:
                query = (
                    select(AllowedOrigin.origin)
                    .join(Bot, Bot.id == AllowedOrigin.bot_id)
                    .where(Bot.is_deleted.is_(False))
                    .where(AllowedOrigin.is_active.is_(True))
                    .where(AllowedOrigin.is_deleted.is_(False))
                )
                
                if bot_key:
                    query = query.where(Bot.bot_key == bot_key)
                elif bot_id:
                    query = query.where(Bot.id == bot_id)
                
                result = await session.execute(query)
                origins = [row[0] for row in result.fetchall()]
            
            if not origins:
                logger.warning(f"No allowed origins found for bot: {cache_identifier}")
                return False
            
            if redis:
                try:
                    pipe = redis.pipeline()
                    pipe.delete(cache_key)
                    for origin_pattern in origins:
                        pipe.sadd(cache_key, origin_pattern)
                    pipe.expire(cache_key, settings.CACHE_ALLOWED_ORIGINS_TTL)
                    await pipe.execute()
                    logger.info(f"Cached {len(origins)} allowed origins for bot: {cache_identifier}")
                except Exception as e:
                    logger.error(f"Failed to cache allowed origins: {e}")
            
            return self._match_origin_patterns(origin, origins)
            
        except Exception as e:
            logger.error(f"Failed to query allowed origins from DB: {e}", exc_info=True)
            return False
    
    def _match_origin_patterns(self, origin: str, patterns: list) -> bool:
        """
        Check if origin matches any pattern (including wildcards).
        
        Examples:
        - Pattern: "https://example.com" matches "https://example.com" and "https://example.com/"
        - Pattern: "https://*.example.com" matches "https://app.example.com"
        - Pattern: "*" matches any origin
        
        Args:
            origin: Request origin
            patterns: List of allowed origin patterns
            
        Returns:
            True if origin matches any pattern
        """
        normalized_origin = origin.rstrip("/")
        
        for pattern in patterns:
            if isinstance(pattern, bytes):
                pattern = pattern.decode('utf-8')

            normalized_pattern = pattern.rstrip("/")
            
            if normalized_pattern == normalized_origin:
                return True
            
            if '*' in normalized_pattern:
                if fnmatch.fnmatch(normalized_origin, normalized_pattern):
                    return True
        
        return False


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Catch and format unhandled exceptions.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler
            
        Returns:
            HTTP response
        """
        try:
            return await call_next(request)
        except Exception as e:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                f"Unhandled exception | Request ID: {request_id} | "
                f"Path: {request.url.path} | Error: {str(e)}",
                exc_info=True
            )
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id
                }
            )


def setup_cors(app) -> None:
    """
    Setup CORS middleware with configuration from settings.
    
    Args:
        app: FastAPI application instance
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )


def setup_middlewares(app) -> None:
    """
    Setup all application middlewares.
    Order matters: last added is executed first.
    
    Args:
        app: FastAPI application instance
    """
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(WidgetCORSMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
