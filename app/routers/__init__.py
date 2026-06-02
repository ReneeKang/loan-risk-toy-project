from app.routers.decisions import router as decisions_router
from app.routers.explanations import router as explanations_router
from app.routers.health import router as health_router
from app.routers.predictions import router as predictions_router
from app.routers.reviews import router as reviews_router

__all__ = [
    "decisions_router",
    "explanations_router",
    "health_router",
    "predictions_router",
    "reviews_router",
]
