from ninja import Router
from .auth import auth_router
from .base import base_router

router = Router()

router.add_router("", base_router)
router.add_router("/auth/", auth_router)
