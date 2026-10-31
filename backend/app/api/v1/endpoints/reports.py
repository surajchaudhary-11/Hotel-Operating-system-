from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_tenant_context, require_roles, TenantContext
from app.models.models import GeneratedReport, ReportSchedule
from app.schemas.schemas import ReportScheduleUpdate
from app.services.night_audit import NightAuditService
from app.services.report_generator import ReportPDFGenerator

router = APIRouter()

@router.post("/trigger-audit")
async def trigger_night_audit(
    audit_date: date = None,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    target_date = audit_date or date.today()
    report = await NightAuditService.run_night_audit(db=db, hotel_id=ctx.hotel_id, audit_date=target_date)
    return {"message": "Night Audit executed successfully", "report": report}

@router.get("/daily")
async def get_daily_report(
    report_date: date = None,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER", "ACCOUNTANT"])),
    db: AsyncSession = Depends(get_db)
):
    target_date = report_date or date.today()
    res = await db.execute(
        select(GeneratedReport).where(
            GeneratedReport.hotel_id == ctx.hotel_id,
            GeneratedReport.report_date == target_date,
            GeneratedReport.report_type == "DAILY_EOD"
        )
    )
    rep = res.scalar_one_or_none()
    if not rep:
        # Run live calculation if report has not run yet today
        report_data = await NightAuditService.run_night_audit(db=db, hotel_id=ctx.hotel_id, audit_date=target_date)
        return report_data
    return rep.report_data

@router.get("/daily/pdf")
async def download_daily_pdf(
    report_date: date = None,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER", "ACCOUNTANT"])),
    db: AsyncSession = Depends(get_db)
):
    target_date = report_date or date.today()
    res = await db.execute(
        select(GeneratedReport).where(
            GeneratedReport.hotel_id == ctx.hotel_id,
            GeneratedReport.report_date == target_date,
            GeneratedReport.report_type == "DAILY_EOD"
        )
    )
    rep = res.scalar_one_or_none()
    report_data = rep.report_data if rep else await NightAuditService.run_night_audit(db=db, hotel_id=ctx.hotel_id, audit_date=target_date)

    pdf_bytes = ReportPDFGenerator.generate_daily_eod_pdf(report_data=report_data, hotel_name=ctx.hotel.name)
    
    filename = f"HotelOS_Daily_Report_{ctx.hotel.slug}_{target_date.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/settings")
async def get_report_schedule_settings(
    ctx: TenantContext = Depends(require_roles(["OWNER"])),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ReportSchedule).where(ReportSchedule.hotel_id == ctx.hotel_id))
    sched = res.scalar_one_or_none()
    if not sched:
        sched = ReportSchedule(
            hotel_id=ctx.hotel_id,
            reporting_time="23:59",
            timezone="Asia/Kolkata",
            whatsapp_recipients=[ctx.hotel.phone],
            email_recipients=[ctx.hotel.email],
            send_pdf_attachment=True,
            is_active=True
        )
        db.add(sched)
        await db.commit()
        await db.refresh(sched)
    return sched

@router.put("/settings")
async def update_report_schedule_settings(
    data: ReportScheduleUpdate,
    ctx: TenantContext = Depends(require_roles(["OWNER"])),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ReportSchedule).where(ReportSchedule.hotel_id == ctx.hotel_id))
    sched = res.scalar_one_or_none()
    if not sched:
        sched = ReportSchedule(hotel_id=ctx.hotel_id)
        db.add(sched)

    sched.reporting_time = data.reporting_time
    sched.timezone = data.timezone
    sched.whatsapp_recipients = data.whatsapp_recipients
    sched.email_recipients = data.email_recipients
    sched.send_pdf_attachment = data.send_pdf_attachment
    sched.is_active = data.is_active

    await db.commit()
    return {"message": "Report schedule settings updated successfully"}

