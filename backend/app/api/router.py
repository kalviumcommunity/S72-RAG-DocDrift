from fastapi import APIRouter
from app.api.v1 import health

api_router = APIRouter()

# Register API v1 sub-routers
api_router.include_router(health.router)
