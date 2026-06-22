from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.routes.analysis import router as analysis_router
from backend.app.api.routes.reports import router as reports_router
from backend.app.api.routes.system import router as system_router


router = APIRouter()
router.include_router(system_router)
router.include_router(analysis_router)
router.include_router(reports_router)
