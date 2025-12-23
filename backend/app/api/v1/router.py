"""
Centralized API router for v1 endpoints.
All routers are registered here and exported to main.py
"""
from fastapi import APIRouter

from app.api.v1 import auth, bots, chat, documents, others, providers, webhooks, widget, notifications, stats
from app.api.v1.admin import users, invites, visitors, tasks


api_router = APIRouter()


api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)


api_router.include_router(
    bots.router,
    prefix="/bots",
    tags=["Bots"]
)


api_router.include_router(
    documents.router,
    prefix="",
    tags=["Documents"]
)


api_router.include_router(
    providers.router,
    prefix="/providers",
    tags=["Providers & Models"]
)


api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"]
)


api_router.include_router(
    users.router,
    prefix="/admin/users",
    tags=["Admin - Users"]
)


api_router.include_router(
    invites.router,
    prefix="/admin/invites",
    tags=["Admin - Invites"]
)


api_router.include_router(
    visitors.router,
    prefix="/admin",
    tags=["Admin - Visitors"]
)


api_router.include_router(
    tasks.router,
    prefix="/admin",
    tags=["Admin - Tasks"]
)


api_router.include_router(
    others.router,
    prefix="/others",
    tags=["Common"]
)

api_router.include_router(
    webhooks.router,
    prefix="",
    tags=["Webhooks"]
)

api_router.include_router(
    widget.router,
    prefix="/widget",
    tags=["Widget"]
)

api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"]
)

api_router.include_router(
    stats.router,
    prefix="",
    tags=["Statistics"]
)

