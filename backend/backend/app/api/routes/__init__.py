from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.courses import router as courses_router
from app.api.routes.uploads import router as uploads_router
from app.api.routes.tutor import router as tutor_router
from app.api.routes.assessments import router as assessments_router
from app.api.routes.learner import router as learner_router
from app.api.routes.evaluation import router as evaluation_router

__all__ = [
    "health_router",
    "auth_router",
    "courses_router",
    "uploads_router",
    "tutor_router",
    "assessments_router",
    "learner_router",
    "evaluation_router",
]
