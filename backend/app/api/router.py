from fastapi import APIRouter
from app.api.v1 import health, documents, workspaces, search, intent, chat

api_router = APIRouter()

# Register API v1 sub-routers
api_router.include_router(health.router)
api_router.include_router(documents.router)
api_router.include_router(workspaces.router)
api_router.include_router(search.router)
api_router.include_router(intent.router)
api_router.include_router(chat.router)


