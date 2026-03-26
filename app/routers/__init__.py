from app.routers.decisions import router as decisions_router
from app.routers.health import router as health_router
from app.routers.predictions import router as predictions_router

__all__ = ["decisions_router", "health_router", "predictions_router"]
