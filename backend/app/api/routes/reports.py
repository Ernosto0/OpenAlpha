from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from backend.app.services.report_service import (
    ReportDetailResponse,
    ReportListItemResponse,
    report_service,
)


router = APIRouter(tags=["reports"])


@router.get("/api/reports", response_model=list[ReportListItemResponse])
async def list_reports() -> list[ReportListItemResponse]:
    return await report_service.list_reports()


@router.get("/api/reports/{report_id}", response_model=ReportDetailResponse)
async def get_report(report_id: str) -> ReportDetailResponse:
    detail = await report_service.get_report_detail(report_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return detail


@router.delete("/api/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: str) -> Response:
    deleted = await report_service.delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
