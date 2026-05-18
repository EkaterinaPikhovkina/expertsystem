from aiogram import Router

from .auth import router as auth_router
from .menu import router as menu_router
from .account import router as account_router
from .diagnostics import router as diagnostics_router
from .ontology_handler import router as ontology_router

all_router = Router()
all_router.include_router(auth_router)
all_router.include_router(menu_router)
all_router.include_router(account_router)
all_router.include_router(diagnostics_router)
all_router.include_router(ontology_router)

__all__ = ["all_router"]
