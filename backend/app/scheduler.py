"""
ARM Platform - APScheduler 기반 월간 알림 스케줄러
매일 09:05 GPS 미체크 직원 알림
매월 1일, 15일, 23일, 25일, 27일, 28일 경비 마감 알림
"""
import os
import logging
from datetime import date, datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.daou_service import DaouOfficeService
from app.utils.database import SessionLocal
from app.models.models import Transaction

logger = logging.getLogger(__name__)

DAOU_CLIENT_ID = os.getenv("DAOU_CLIENT_ID", "")
DAOU_CLIENT_SECRET = os.getenv("DAOU_CLIENT_SECRET", "")
SERVER_URL = os.getenv("SERVER_URL", "https://13.125.110.156")

daou = DaouOfficeService(DAOU_CLIENT_ID, DAOU_CLIENT_SECRET, SERVER_URL)
scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


def get_active_employees():
    """DB에서 활성 직원 목록 조회"""
    db = SessionLocal()
    try:
        from sqlalchemy import text
        result = db.execute(text("SELECT DISTINCT emp_no FROM cards WHERE is_active = TRUE")).fetchall()
        return [row[0] for row in result if row[0]]
    except Exception as e:
        logger.error(f"직원 목록 조회 실패: {e}")
        return []
    finally:
        db.close()


def get_pending_expenses(emp_no: str):
    """미처리 경비 건수/금액 조회"""
    db = SessionLocal()
    try:
        current_month = date.today().replace(day=1)
        rows = db.query(Transaction).filter(
            Transaction.daou_approval_status == "PENDING",
            Transaction.trans_date >= current_month
        ).all()
        emp_rows = [r for r in rows]  # 실제로는 emp_no 필터 추가
        return emp_rows
    except Exception as e:
        logger.error(f"미처리 경비 조회 실패: {e}")
        return []
    finally:
        db.close()


# ─────────────────────────────────────────
# 매일 09:05 GPS 미체크 직원 알림
# ─────────────────────────────────────────
@scheduler.scheduled_job(CronTrigger(hour=9, minute=5))
async def daily_gps_reminder():
    logger.info("📍 일일 GPS 체크 리마인더 실행")
    employees = get_active_employees()
    for emp_no in employees:
        try:
            has_gps = await daou.check_gps_today(emp_no)
            if not has_gps:
                pending = get_pending_expenses(emp_no)
                if pending:
                    total = sum(p.amount for p in pending)
                    await daou.send_notification(
                        emp_no,
                        f"📍 오늘 GPS 출근 체크가 없어요!\n"
                        f"미처리 경비: {len(pending)}건 ({total:,}원)\n"
                        f"GPS 체크 후 영수증을 제출하면 즉시 자동 처리됩니다! 💡"
                    )
        except Exception as e:
            logger.error(f"GPS 리마인더 오류 (emp: {emp_no}): {e}")


# ─────────────────────────────────────────
# 매월 1일 09:00 경비 접수 시작 공지
# ─────────────────────────────────────────
@scheduler.scheduled_job(CronTrigger(day=1, hour=9, minute=0))
async def monthly_start_notice():
    logger.info("📢 월간 경비 접수 시작 공지")
    employees = get_active_employees()
    month = date.today().strftime("%Y년 %m월")
    if employees:
        await daou.send_bulk_notification(
            employees,
            f"📋 {month} 경비 접수가 시작되었습니다!\n"
            f"✅ 영수증 사진을 업로드하면 자동으로 경비 처리됩니다.\n"
            f"📅 접수 마감: 이번 달 28일\n"
            f"💡 GPS 출근 체크 시 D+1 즉시 정산!"
        )


# ─────────────────────────────────────────
# 매월 15일 09:00 중간 점검 알림
# ─────────────────────────────────────────
@scheduler.scheduled_job(CronTrigger(day=15, hour=9, minute=0))
async def mid_month_reminder():
    logger.info("📊 월간 경비 중간 점검 알림")
    employees = get_active_employees()
    for emp_no in employees:
        pending = get_pending_expenses(emp_no)
        if pending:
            total = sum(p.amount for p in pending)
            await daou.send_notification(
                emp_no,
                f"📊 경비 처리 중간 점검 (D-13)\n"
                f"미처리 경비: {len(pending)}건 ({total:,}원)\n"
                f"⏰ 마감까지 13일 남았습니다. 서둘러 제출해주세요!"
            )


# ─────────────────────────────────────────
# 마감 D-7/D-5/D-3 알림
# ─────────────────────────────────────────
@scheduler.scheduled_job(CronTrigger(day=23, hour=9, minute=0))
async def deadline_d7():
    await _deadline_reminder(days_left=7)


@scheduler.scheduled_job(CronTrigger(day=25, hour=9, minute=0))
async def deadline_d5():
    await _deadline_reminder(days_left=5)


@scheduler.scheduled_job(CronTrigger(day=27, hour=9, minute=0))
async def deadline_d3():
    await _deadline_reminder(days_left=3)


async def _deadline_reminder(days_left: int):
    logger.info(f"⏰ 경비 마감 D-{days_left} 알림")
    employees = get_active_employees()
    for emp_no in employees:
        pending = get_pending_expenses(emp_no)
        if pending:
            total = sum(p.amount for p in pending)
            emoji = "🚨" if days_left <= 3 else "⏰"
            await daou.send_notification(
                emp_no,
                f"{emoji} 경비 마감 D-{days_left}!\n"
                f"미처리 경비: {len(pending)}건 ({total:,}원)\n"
                f"📅 28일까지 제출하지 않으면 다음 달로 이월됩니다!\n"
                f"지금 바로 제출하세요 👉"
            )


# ─────────────────────────────────────────
# 매월 28일 09:00 마감 최종 알림
# ─────────────────────────────────────────
@scheduler.scheduled_job(CronTrigger(day=28, hour=9, minute=0))
async def final_deadline_morning():
    logger.info("🚨 최종 마감일 오전 알림")
    employees = get_active_employees()
    for emp_no in employees:
        pending = get_pending_expenses(emp_no)
        if pending:
            total = sum(p.amount for p in pending)
            await daou.send_notification(
                emp_no,
                f"🚨 오늘이 경비 접수 마감일입니다!\n"
                f"미처리: {len(pending)}건 ({total:,}원)\n"
                f"⏰ 오늘 17:00까지 미제출 시 다음 달로 이월됩니다!\n"
                f"지금 즉시 제출해주세요!"
            )


# ─────────────────────────────────────────
# 매월 28일 17:00 접수 마감 처리
# ─────────────────────────────────────────
@scheduler.scheduled_job(CronTrigger(day=28, hour=17, minute=0))
async def close_monthly_expense():
    logger.info("🔒 월간 경비 접수 마감 처리")
    db = SessionLocal()
    try:
        current_month = date.today().replace(day=1)
        result = db.execute(
            __import__("sqlalchemy").text(
                "UPDATE transactions SET daou_approval_status = 'CLOSED' "
                "WHERE daou_approval_status = 'PENDING' "
                "AND trans_date >= :start_date"
            ),
            {"start_date": current_month}
        )
        db.commit()
        logger.info(f"마감 처리 완료: {result.rowcount}건 이월")
    finally:
        db.close()


def start_scheduler():
    """스케줄러 시작"""
    if not scheduler.running:
        scheduler.start()
        logger.info("✅ ARM 알림 스케줄러 시작됨")
