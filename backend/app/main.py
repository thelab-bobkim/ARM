"""
ARM Platform - FastAPI Main Application
영수증 업로드 → OCR → 경비코드 매핑 → GPS 검증 → 다우오피스 전자결재 자동 생성
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

from app.utils.database import get_db, engine
from app.models.models import Base, Transaction, Card, ApprovalLog, MerchantMapping
from app.services.ocr_service import OCRService
from app.services.expense_mapping import ExpenseCodeMappingService
from app.services.gps_validation import GPSValidationEngine
from app.services.daou_service import DaouOfficeService
from app.services.merchant_location import MerchantLocationService
from app.adapters.factory import get_adapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경변수
DAOU_CLIENT_ID = os.getenv("DAOU_CLIENT_ID", "")
DAOU_CLIENT_SECRET = os.getenv("DAOU_CLIENT_SECRET", "")
SERVER_URL = os.getenv("SERVER_URL", "https://13.125.110.156")

daou_service = DaouOfficeService(DAOU_CLIENT_ID, DAOU_CLIENT_SECRET, SERVER_URL)
ocr_service = OCRService()
mapping_service = ExpenseCodeMappingService()
gps_engine = GPSValidationEngine()
location_service = MerchantLocationService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서비스 시작 시 DB 테이블 생성
    Base.metadata.create_all(bind=engine)
    logger.info("✅ ARM Platform 서비스 시작")
    yield
    logger.info("🛑 ARM Platform 서비스 종료")


app = FastAPI(
    title="ARM 경비자동청구 플랫폼",
    version="2.0.0",
    description="다우오피스 연동 법인카드 경비 자동처리 시스템",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────
# Pydantic 스키마
# ─────────────────────────────────────────
class TransactionQuery(BaseModel):
    card_company: str
    corp_id: str
    card_numbers: List[str]
    from_date: date
    to_date: date


class CallbackPayload(BaseModel):
    docId: Optional[str] = None
    status: Optional[str] = None
    empNo: Optional[str] = None
    partnerDocId: Optional[str] = None


class GpsRetryRequest(BaseModel):
    emp_no: str
    receipt_date: Optional[str] = None


class ExemptSubmitRequest(BaseModel):
    emp_no: str
    receipt: Optional[dict] = None
    expense_code: Optional[dict] = None
    exempt_reason: str


# ─────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ARM Platform", "version": "2.0.0"}


# ─────────────────────────────────────────
# 영수증 업로드 → 전체 자동 처리 파이프라인
# ─────────────────────────────────────────
@app.post("/api/receipts/upload")
async def upload_receipt(
    file: UploadFile = File(...),
    emp_no: str = Form(...),
    capture_lat: Optional[float] = Form(None),   # 📍 촬영 시 GPS 위도
    capture_lng: Optional[float] = Form(None),   # 📍 촬영 시 GPS 경도
    db: Session = Depends(get_db)
):
    """
    메인 파이프라인 v2.1 (실시간 GPS 검증 추가):
    1. 영수증 OCR
    2. 경비코드 자동 매핑
    3. GPS 검증
       - capture_lat/lng 있음 → 실시간 위치 기반 (가맹점 거리 계산)
       - capture_lat/lng 없음 → 다우오피스 출근 기록 기반 (기존 방식)
    4. GREEN → 자동 전자결재 / YELLOW → 검토 / RED → 반려
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "이미지 파일만 업로드 가능합니다.")

    image_bytes = await file.read()

    # 1. OCR 처리
    logger.info(f"[{emp_no}] OCR 처리 시작")
    receipt_data = await ocr_service.extract_receipt(image_bytes)
    if receipt_data.get("error"):
        raise HTTPException(500, f"OCR 처리 실패: {receipt_data['error']}")

    # 2. 경비코드 자동 매핑
    expense_code = await mapping_service.get_expense_code(
        receipt_data.get("merchant", ""),
        receipt_data.get("mcc_code", ""),
        db
    )
    logger.info(f"[{emp_no}] 경비코드 매핑: {expense_code['code']} ({expense_code['source']})")

    # 3. GPS 검증 - 실시간 위치 우선, 없으면 출근 기록 사용
    gps_mode = "REALTIME" if (capture_lat and capture_lng) else "ATTENDANCE"

    if gps_mode == "REALTIME":
        # 📍 신규: 촬영 위치 ↔ 가맹점 위치 비교
        logger.info(f"[{emp_no}] 실시간 GPS 검증: ({capture_lat:.4f}, {capture_lng:.4f})")
        gps_result = await location_service.validate(
            merchant_name=receipt_data.get("merchant", ""),
            capture_lat=capture_lat,
            capture_lng=capture_lng,
        )
        gps_result["mode"] = "REALTIME"
    else:
        # 기존: 다우오피스 출근 GPS 기록 비교
        logger.info(f"[{emp_no}] 출근기록 GPS 검증 (위치정보 없음)")
        gps_logs = await daou_service.get_attendance_gps(emp_no, receipt_data.get("date", ""))
        gps_result = gps_engine.calculate_trust_score(receipt_data, gps_logs)
        gps_result["mode"] = "ATTENDANCE"

    logger.info(f"[{emp_no}] GPS 검증결과: {gps_result['grade']} ({gps_result['score']}점) [{gps_mode}]")

    # 4. 등급별 처리
    result = await _process_by_grade(emp_no, receipt_data, expense_code, gps_result, db)

    return JSONResponse({
        "receipt": {
            "merchant": receipt_data.get("merchant"),
            "date": receipt_data.get("date"),
            "amount": receipt_data.get("amount"),
            "ocr_engine": receipt_data.get("ocr_engine")
        },
        "expense_code": expense_code,
        "gps": gps_result,
        "result": result
    })


# ─────────────────────────────────────────
# GPS 재검증 (다우오피스 출근 후 재시도)
# ─────────────────────────────────────────
@app.post("/api/receipts/gps-retry")
async def gps_retry(req: GpsRetryRequest):
    """다우오피스 GPS 등록 후 재검증"""
    gps_logs = await daou_service.get_attendance_gps(req.emp_no, req.receipt_date or "")
    if gps_logs:
        return {"gps": {"score": 80, "grade": "GREEN", "details": ["GPS 출근 기록 확인됨"],
                        "mode": "ATTENDANCE_RETRY"},
                "result": {"status": "RETRY_READY"}}
    return {"gps": {"score": 25, "grade": "RED", "details": ["GPS 출근 기록 없음"],
                    "mode": "ATTENDANCE_RETRY"},
            "result": {"status": "REJECTED"}}


# ─────────────────────────────────────────
# GPS 면제 사유 제출 (담당자 검토 요청)
# ─────────────────────────────────────────
@app.post("/api/receipts/exempt-submit")
async def exempt_submit(req: ExemptSubmitRequest):
    """GPS 면제 사유 입력 후 담당자 검토 요청"""
    await daou_service.send_notification(
        req.emp_no,
        f"📋 GPS 면제 검토 요청\n"
        f"직원: {req.emp_no}\n"
        f"가맹점: {req.receipt.get('merchant') if req.receipt else '-'}\n"
        f"금액: {req.receipt.get('amount', 0):,}원\n"
        f"사유: {req.exempt_reason}"
    )
    return {"status": "submitted", "message": "담당자 검토 요청이 전송되었습니다."}


async def _process_by_grade(emp_no, receipt, expense_code, gps_result, db):
    grade = gps_result["grade"]

    if grade == "GREEN":
        approval = await daou_service.create_expense_approval(
            receipt, emp_no, expense_code, gps_result
        )
        await daou_service.send_notification(
            emp_no,
            f"✅ 경비 자동처리 완료!\n"
            f"💰 {receipt.get('amount', 0):,}원 | 📍 GPS {gps_result['score']}점\n"
            f"📋 {receipt.get('merchant', '')} ({receipt.get('date', '')})\n"
            f"결재선이 자동 생성되었습니다.",
            link_url=approval.get("redirect_url")
        )
        return {"status": "AUTO_APPROVED", "approval": approval}

    elif grade == "YELLOW":
        await daou_service.send_notification(
            emp_no,
            f"⚠️ 경비 검토 필요\n"
            f"GPS 점수: {gps_result['score']}점 → 담당자 확인 중\n"
            f"💰 {receipt.get('amount', 0):,}원 | {receipt.get('merchant', '')}\n"
            f"사유: {', '.join(gps_result['details'])}"
        )
        return {"status": "NEEDS_REVIEW", "gps_score": gps_result["score"]}

    else:  # RED
        deeplink = "daouoffice://attendance/checkin"
        await daou_service.send_notification(
            emp_no,
            f"❌ 경비 처리 불가\n"
            f"GPS 점수: {gps_result['score']}점 (기준: 50점 이상)\n"
            f"💡 GPS 출근 체크 후 재시도하시면 자동 처리됩니다.\n"
            f"사유: {', '.join(gps_result['details'])}",
            link_url=deeplink
        )
        return {"status": "REJECTED", "gps_score": gps_result["score"], "details": gps_result["details"]}


# ─────────────────────────────────────────
# 카드 거래내역 조회
# ─────────────────────────────────────────
@app.post("/api/transactions")
async def fetch_transactions(query: TransactionQuery, db: Session = Depends(get_db)):
    """카드사 API → 거래내역 조회 및 DB 저장"""
    try:
        adapter = get_adapter(query.card_company)
        transactions = await adapter.fetch_transactions(
            query.corp_id, query.card_numbers, query.from_date, query.to_date
        )
        return {
            "card_company": query.card_company,
            "count": len(transactions),
            "transactions": [
                {
                    "merchant": t.merchant,
                    "trans_date": t.trans_date.isoformat(),
                    "amount": t.amount,
                    "vat": t.vat,
                    "mcc_code": t.mcc_code,
                    "approval_no": t.approval_no,
                    "card_number_masked": t.card_number_masked
                }
                for t in transactions
            ]
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────
# 다우오피스 결재 콜백
# ─────────────────────────────────────────
@app.post("/api/daou/callback")
async def daou_callback(payload: CallbackPayload, db: Session = Depends(get_db)):
    """다우오피스 결재 상태 변경 콜백 처리"""
    logger.info(f"결재 콜백 수신: docId={payload.docId}, status={payload.status}")

    log = db.query(ApprovalLog).filter(
        ApprovalLog.daou_doc_id == payload.docId
    ).first()

    if log:
        log.status = payload.status
        log.callback_data = payload.dict()
        log.updated_at = datetime.now()
        db.commit()

        # 결재 완료 알림
        if payload.status == "APPROVED":
            await daou_service.send_notification(
                log.emp_no,
                f"✅ 경비 승인 완료!\n"
                f"💰 {log.amount:,}원이 다음 정산일에 지급됩니다.\n"
                f"감사합니다!"
            )
        elif payload.status == "REJECTED":
            await daou_service.send_notification(
                log.emp_no,
                f"❌ 경비가 반려되었습니다.\n"
                f"다우오피스에서 반려 사유를 확인하고 재제출해주세요."
            )

    return {"status": "OK"}


# ─────────────────────────────────────────
# 경비코드 관리 API
# ─────────────────────────────────────────
@app.get("/api/expense-codes")
async def get_expense_codes(db: Session = Depends(get_db)):
    """경비코드 목록 조회"""
    from app.models.models import ExpenseCode
    codes = db.query(ExpenseCode).filter(ExpenseCode.is_active == True).all()
    return [{"code": c.code, "name": c.name, "description": c.description} for c in codes]


@app.get("/api/merchant-mappings")
async def get_merchant_mappings(db: Session = Depends(get_db)):
    """가맹점-경비코드 매핑 목록"""
    mappings = db.query(MerchantMapping).order_by(
        MerchantMapping.use_count.desc()
    ).limit(100).all()
    return [
        {
            "id": m.id,
            "merchant_pattern": m.merchant_pattern,
            "expense_code": m.expense_code,
            "expense_name": m.expense_name,
            "source": m.source,
            "use_count": m.use_count
        }
        for m in mappings
    ]


@app.post("/api/merchant-mappings")
async def create_merchant_mapping(
    merchant_pattern: str = Form(...),
    expense_code: str = Form(...),
    expense_name: str = Form(...),
    db: Session = Depends(get_db)
):
    """가맹점-경비코드 수동 매핑 추가"""
    mapping = MerchantMapping(
        merchant_pattern=merchant_pattern,
        expense_code=expense_code,
        expense_name=expense_name,
        source="MANUAL",
        confidence=1.0
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return {"id": mapping.id, "status": "created"}


# ─────────────────────────────────────────
# 대시보드 통계
# ─────────────────────────────────────────
@app.get("/api/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """월간 경비 처리 통계"""
    from sqlalchemy import func
    current_month = datetime.now().replace(day=1).date()

    stats = db.query(
        Transaction.daou_approval_status,
        func.count(Transaction.id).label("count"),
        func.sum(Transaction.amount).label("total_amount")
    ).filter(
        Transaction.trans_date >= current_month
    ).group_by(Transaction.daou_approval_status).all()

    return {
        "month": current_month.strftime("%Y-%m"),
        "by_status": [
            {"status": s.daou_approval_status, "count": s.count, "total_amount": s.total_amount or 0}
            for s in stats
        ]
    }
