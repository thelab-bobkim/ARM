"""
ARM Platform - FastAPI Main Application
영수증 업로드 / 사용자 프로필 / 거래 동기화 / 경비코드 매핑 / 히스토리 조회
"""
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.adapters.factory import get_adapter
from app.models.models import (
    ApprovalLog,
    Base,
    Card,
    ExpenseCode,
    ExpenseItem,
    MerchantMapping,
    Transaction,
    UserProfile,
)
from app.services.daou_service import DaouOfficeService
from app.services.expense_mapping import ExpenseCodeMappingService
from app.services.gps_validation import GPSValidationEngine
from app.services.merchant_location import MerchantLocationService
from app.services.ocr_service import OCRService
from app.utils.database import engine, get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DAOU_CLIENT_ID = os.getenv("DAOU_CLIENT_ID", "")
DAOU_CLIENT_SECRET = os.getenv("DAOU_CLIENT_SECRET", "")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")
UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", "/app/uploads")).resolve()
RECEIPT_UPLOAD_DIR = UPLOAD_ROOT / "receipts"
ENABLE_DEMO_SEED = os.getenv("ENABLE_DEMO_SEED", "false").lower() == "true"

ocr_service = OCRService()
mapping_service = ExpenseCodeMappingService()
gps_engine = GPSValidationEngine()
daou_service = DaouOfficeService(DAOU_CLIENT_ID, DAOU_CLIENT_SECRET, SERVER_URL)
merchant_location_service = MerchantLocationService()


DEFAULT_EXPENSE_CODES = [
    {"code": "MEAL_EXP", "name": "식대", "description": "식사 및 다과 비용"},
    {"code": "TRANS_LOCAL", "name": "대중교통", "description": "버스/지하철"},
    {"code": "TRANS_TRAIN", "name": "기차/KTX", "description": "기차/철도"},
    {"code": "TRANS_AIR", "name": "항공", "description": "항공권"},
    {"code": "TRANS_TAXI", "name": "택시", "description": "택시 및 대리운전"},
    {"code": "TRANS_FUEL", "name": "주유비", "description": "주유 및 충전"},
    {"code": "TRANS_PARKING", "name": "주차비", "description": "주차 및 통행료"},
    {"code": "LODGING_EXP", "name": "숙박비", "description": "숙박/호텔"},
    {"code": "OFFICE_SUPPLY", "name": "사무용품", "description": "도서 및 사무소모품"},
    {"code": "SW_SERVICE", "name": "소프트웨어/서비스", "description": "SaaS/클라우드"},
    {"code": "COMM_EXP", "name": "통신비", "description": "통신/인터넷"},
    {"code": "MEDICAL_EXP", "name": "의료비", "description": "의료/약국"},
    {"code": "EDU_EXP", "name": "교육비", "description": "교육 및 세미나"},
    {"code": "WELFARE_EXP", "name": "복리후생", "description": "문화/복지"},
    {"code": "OTHER_EXP", "name": "기타경비", "description": "기타"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    RECEIPT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    db = next(get_db())
    try:
        ensure_expense_codes_seeded(db)
    finally:
        db.close()
    logger.info("✅ ARM Platform started")
    yield
    logger.info("🛑 ARM Platform stopped")


app = FastAPI(
    title="ARM 경비자동청구 플랫폼",
    version="2.1.0",
    description="다우오피스 연동 경비 자동화 플랫폼",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")


class TransactionQuery(BaseModel):
    card_company: str
    corp_id: str
    card_numbers: List[str]
    from_date: date
    to_date: date
    emp_no: Optional[str] = None
    employee_name: Optional[str] = None
    department: Optional[str] = None
    project_code: Optional[str] = None
    save_to_db: bool = True


class UserProfileRequest(BaseModel):
    daou_login_id: Optional[str] = None
    employee_name: Optional[str] = None
    department: Optional[str] = None
    project_code: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = "MANUAL"


class MerchantMappingRequest(BaseModel):
    merchant_pattern: str = Field(..., min_length=1)
    expense_code: str = Field(..., min_length=1)
    expense_name: str = Field(..., min_length=1)
    mcc_code: Optional[str] = None


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


def normalize_emp_no(emp_no: str) -> str:
    value = (emp_no or "").strip()
    if "@" in value:
        value = value.split("@", 1)[0]
    return value.strip()


def parse_receipt_date(value: Optional[str]) -> date:
    if not value:
        return datetime.now().date()
    try:
        return datetime.fromisoformat(value.replace("Z", "")).date()
    except Exception:
        return datetime.now().date()


def save_receipt_image(file_name: str, image_bytes: bytes, emp_no: str, receipt_date: Optional[str] = None) -> str:
    target_date = parse_receipt_date(receipt_date)
    date_dir = RECEIPT_UPLOAD_DIR / target_date.strftime("%Y/%m/%d")
    date_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file_name or "receipt.jpg").suffix.lower() or ".jpg"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_emp_no = normalize_emp_no(emp_no) or "unknown"
    filename = f"{safe_emp_no}_{timestamp}_{uuid4().hex[:8]}{ext}"
    abs_path = date_dir / filename
    abs_path.write_bytes(image_bytes)
    relative = abs_path.relative_to(UPLOAD_ROOT)
    return f"/uploads/{relative.as_posix()}"


def receipt_absolute_path(receipt_url: Optional[str]) -> Optional[Path]:
    if not receipt_url or not receipt_url.startswith("/uploads/"):
        return None
    relative = receipt_url.replace("/uploads/", "", 1)
    return (UPLOAD_ROOT / relative).resolve()


def receipt_file_exists(receipt_url: Optional[str]) -> bool:
    abs_path = receipt_absolute_path(receipt_url)
    return bool(abs_path and abs_path.exists())


def serialize_profile(profile: Optional[UserProfile]) -> dict:
    if not profile:
        return {}
    return {
        "emp_no": profile.emp_no,
        "daou_login_id": profile.daou_login_id,
        "employee_name": profile.employee_name,
        "department": profile.department,
        "project_code": profile.project_code,
        "email": profile.email,
        "source": profile.source,
        "synced_at": profile.synced_at.isoformat() if profile.synced_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def get_or_create_user_profile(db: Session, emp_no: str) -> UserProfile:
    normalized = normalize_emp_no(emp_no)
    profile = db.query(UserProfile).filter(UserProfile.emp_no == normalized).first()
    if profile:
        return profile
    profile = UserProfile(emp_no=normalized, daou_login_id=normalized)
    db.add(profile)
    db.flush()
    return profile


def apply_profile_updates(profile: UserProfile, payload: dict) -> UserProfile:
    for field in ["daou_login_id", "employee_name", "department", "project_code", "email", "source"]:
        if field in payload and payload[field] is not None:
            setattr(profile, field, payload[field])
    return profile


def ensure_expense_codes_seeded(db: Session):
    exists = db.query(ExpenseCode).count()
    if exists:
        return
    for item in DEFAULT_EXPENSE_CODES:
        db.add(ExpenseCode(**item, is_active=True))
    db.commit()


def mask_card_number(card_number: str) -> str:
    digits = "".join(ch for ch in (card_number or "") if ch.isdigit())
    return ("*" * max(0, len(digits) - 4)) + digits[-4:] if digits else ""


def upsert_card_record(db: Session, card_company: str, card_number_masked: str, corp_id: str, emp_no: str) -> Card:
    card = db.query(Card).filter(
        Card.card_company == card_company,
        Card.card_number_masked == card_number_masked,
    ).first()
    if card:
        card.corp_id = corp_id
        card.emp_no = emp_no or card.emp_no
        card.is_active = True
        return card
    card = Card(
        card_company=card_company,
        card_number_masked=card_number_masked,
        corp_id=corp_id,
        emp_no=emp_no,
        is_active=True,
    )
    db.add(card)
    db.flush()
    return card


async def persist_card_transactions(db: Session, query: TransactionQuery, transactions: list) -> dict:
    imported = 0
    skipped = 0
    expense_items = 0
    normalized_emp = normalize_emp_no(query.emp_no or "")

    for txn in transactions:
        approval_no = txn.approval_no or f"{txn.card_company}-{txn.trans_date.strftime('%Y%m%d')}-{txn.amount}-{txn.card_number_masked[-4:]}"
        source_ref = f"CARD:{txn.card_company}:{approval_no}"
        existing = db.query(Transaction).filter(
            or_(Transaction.approval_no == approval_no, Transaction.source_ref == source_ref)
        ).first()
        if existing:
            skipped += 1
            continue

        expense_code = await mapping_service.get_expense_code(txn.merchant, txn.mcc_code, db)
        card = upsert_card_record(db, txn.card_company, txn.card_number_masked, query.corp_id, normalized_emp)

        trans = Transaction(
            card_id=card.id,
            emp_no=normalized_emp,
            employee_name=query.employee_name,
            department=query.department,
            project_code=query.project_code,
            source_type="CARD",
            source_ref=source_ref,
            trans_date=txn.trans_date,
            trans_time=txn.trans_time,
            merchant=txn.merchant,
            mcc_code=txn.mcc_code,
            amount=txn.amount,
            vat=txn.vat,
            installment=txn.installment,
            approval_no=approval_no,
            expense_code=expense_code.get("code"),
            expense_name=expense_code.get("name"),
            expense_code_source=expense_code.get("source"),
            daou_approval_status="PENDING",
            raw_data=txn.raw_data,
        )
        db.add(trans)
        db.flush()

        item = ExpenseItem(
            source_type="CARD",
            source_ref=source_ref,
            transaction_id=trans.id,
            emp_no=normalized_emp or "UNASSIGNED",
            employee_name=query.employee_name,
            department=query.department,
            project_code=query.project_code,
            txn_date=txn.trans_date,
            merchant=txn.merchant,
            amount=txn.amount,
            vat=txn.vat,
            payment_method=f"{txn.card_company} 법인카드",
            usage_type=expense_code.get("name"),
            usage_detail=f"{txn.card_company} 카드 승인 {approval_no}",
            evidence_url=None,
            gps_grade=None,
            gps_score=None,
            status="INBOX",
            raw_data=txn.raw_data,
        )
        db.add(item)
        imported += 1
        expense_items += 1

    db.commit()
    return {"imported": imported, "skipped": skipped, "expense_items": expense_items}


def persist_receipt_history(
    db: Session,
    emp_no: str,
    receipt: dict,
    expense_code: dict,
    gps_result: dict,
    result: dict,
    receipt_image_url: str,
    employee_name: Optional[str] = None,
    department: Optional[str] = None,
    project_code: Optional[str] = None,
):
    txn_date = parse_receipt_date(receipt.get("date"))
    approval_no = receipt.get("approval_no") or f"RCT-{normalize_emp_no(emp_no)}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:4]}"
    source_ref = f"RECEIPT:{approval_no}"

    existing = db.query(Transaction).filter(Transaction.source_ref == source_ref).first()
    if existing:
        return existing, db.query(ExpenseItem).filter(ExpenseItem.source_ref == source_ref).first()

    trans = Transaction(
        emp_no=normalize_emp_no(emp_no),
        employee_name=employee_name,
        department=department,
        project_code=project_code,
        source_type="RECEIPT",
        source_ref=source_ref,
        trans_date=txn_date,
        trans_time=receipt.get("time"),
        merchant=receipt.get("merchant"),
        mcc_code=receipt.get("mcc_code"),
        amount=int(receipt.get("amount") or 0),
        vat=int(receipt.get("vat") or 0),
        installment=0,
        approval_no=approval_no,
        expense_code=expense_code.get("code"),
        expense_name=expense_code.get("name"),
        expense_code_source=expense_code.get("source"),
        daou_approval_id=(result.get("approval") or {}).get("doc_id"),
        daou_approval_status=(result.get("approval") or {}).get("status") or result.get("status"),
        gps_score=gps_result.get("score"),
        gps_grade=gps_result.get("grade"),
        receipt_image_path=receipt_image_url,
        raw_data={
            "receipt": receipt,
            "expense_code": expense_code,
            "gps": gps_result,
            "result": result,
        },
    )
    db.add(trans)
    db.flush()

    item = ExpenseItem(
        source_type="RECEIPT",
        source_ref=source_ref,
        transaction_id=trans.id,
        emp_no=normalize_emp_no(emp_no),
        employee_name=employee_name,
        department=department,
        project_code=project_code,
        txn_date=txn_date,
        merchant=receipt.get("merchant"),
        amount=int(receipt.get("amount") or 0),
        vat=int(receipt.get("vat") or 0),
        payment_method="영수증",
        usage_type=expense_code.get("name"),
        usage_detail=receipt.get("category") or receipt.get("raw_text", "")[:200],
        evidence_url=receipt_image_url,
        gps_grade=gps_result.get("grade"),
        gps_score=gps_result.get("score"),
        status=result.get("status"),
        raw_data={
            "receipt": receipt,
            "expense_code": expense_code,
            "gps": gps_result,
            "result": result,
        },
    )
    db.add(item)
    db.flush()

    approval = result.get("approval") or {}
    if approval.get("status") == "created":
        db.add(
            ApprovalLog(
                transaction_id=trans.id,
                daou_doc_id=approval.get("doc_id"),
                emp_no=normalize_emp_no(emp_no),
                amount=trans.amount,
                status="PENDING",
                callback_data=approval,
            )
        )

    db.commit()
    db.refresh(trans)
    db.refresh(item)
    return trans, item


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "ARM Platform",
        "version": "2.1.0",
        "upload_root": str(UPLOAD_ROOT),
        "demo_seed_enabled": ENABLE_DEMO_SEED,
    }


@app.get("/api/system/features")
async def system_features():
    return {
        "demo_seed_enabled": ENABLE_DEMO_SEED,
        "receipt_upload_root": str(RECEIPT_UPLOAD_DIR),
        "daou": daou_service.validate_config(),
    }


@app.get("/api/expense-codes")
async def get_expense_codes(db: Session = Depends(get_db)):
    codes = db.query(ExpenseCode).filter(ExpenseCode.is_active == True).order_by(ExpenseCode.code.asc()).all()
    return [
        {
            "code": c.code,
            "name": c.name,
            "description": c.description,
        }
        for c in codes
    ]


@app.get("/api/user-profiles/{emp_no}")
async def get_user_profile(
    emp_no: str,
    sync_daou: bool = Query(False),
    db: Session = Depends(get_db),
):
    normalized = normalize_emp_no(emp_no)
    profile = db.query(UserProfile).filter(UserProfile.emp_no == normalized).first()
    if sync_daou and normalized:
        daou_profile = await daou_service.fetch_employee_profile(normalized)
        if daou_profile:
            if not profile:
                profile = UserProfile(emp_no=normalized)
                db.add(profile)
            apply_profile_updates(profile, daou_profile)
            profile.synced_at = datetime.now()
            db.commit()
            db.refresh(profile)
    if not profile:
        profile = get_or_create_user_profile(db, normalized)
        db.commit()
        db.refresh(profile)
    return serialize_profile(profile)


@app.put("/api/user-profiles/{emp_no}")
async def upsert_user_profile(emp_no: str, payload: UserProfileRequest, db: Session = Depends(get_db)):
    profile = get_or_create_user_profile(db, emp_no)
    apply_profile_updates(profile, payload.model_dump())
    db.commit()
    db.refresh(profile)
    return serialize_profile(profile)


@app.post("/api/user-profiles/{emp_no}/sync-daou")
async def sync_user_profile_from_daou(emp_no: str, db: Session = Depends(get_db)):
    normalized = normalize_emp_no(emp_no)
    daou_profile = await daou_service.fetch_employee_profile(normalized)
    if not daou_profile:
        raise HTTPException(404, "다우오피스에서 사용자 정보를 찾지 못했습니다.")
    profile = get_or_create_user_profile(db, normalized)
    apply_profile_updates(profile, daou_profile)
    profile.synced_at = datetime.now()
    db.commit()
    db.refresh(profile)
    return serialize_profile(profile)


@app.post("/api/receipts/upload")
async def upload_receipt(
    file: UploadFile = File(...),
    emp_no: str = Form(...),
    employee_name: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    project_code: Optional[str] = Form(None),
    capture_lat: Optional[float] = Form(None),
    capture_lng: Optional[float] = Form(None),
    db: Session = Depends(get_db),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "이미지 파일만 업로드 가능합니다.")

    normalized_emp = normalize_emp_no(emp_no)
    if not normalized_emp:
        raise HTTPException(400, "emp_no가 필요합니다.")

    profile = get_or_create_user_profile(db, normalized_emp)
    payload_updates = {
        "daou_login_id": normalized_emp,
        "employee_name": employee_name or profile.employee_name,
        "department": department or profile.department,
        "project_code": project_code or profile.project_code,
        "source": profile.source or "MANUAL",
    }
    apply_profile_updates(profile, payload_updates)
    db.flush()

    image_bytes = await file.read()
    receipt_data = await ocr_service.extract_receipt(image_bytes)
    if receipt_data.get("error"):
        raise HTTPException(500, f"OCR 처리 실패: {receipt_data['error']}")

    receipt_image_url = save_receipt_image(file.filename, image_bytes, normalized_emp, receipt_data.get("date"))
    expense_code = await mapping_service.get_expense_code(
        receipt_data.get("merchant", ""),
        receipt_data.get("mcc_code", ""),
        db,
    )

    if capture_lat is not None and capture_lng is not None:
        gps_result = await merchant_location_service.validate(
            merchant_name=receipt_data.get("merchant", ""),
            capture_lat=capture_lat,
            capture_lng=capture_lng,
            address_hint=receipt_data.get("address", ""),
        )
        gps_result["mode"] = "REALTIME"
    else:
        gps_logs = await daou_service.get_attendance_gps(normalized_emp, receipt_data.get("date", ""))
        gps_result = gps_engine.calculate_trust_score(receipt_data, gps_logs)
        gps_result["mode"] = "ATTENDANCE"

    receipt_payload = {
        **receipt_data,
        "receipt_image_url": receipt_image_url,
        "evidence_url": receipt_image_url,
    }
    result = await _process_by_grade(normalized_emp, receipt_payload, expense_code, gps_result)
    trans, item = persist_receipt_history(
        db=db,
        emp_no=normalized_emp,
        receipt=receipt_payload,
        expense_code=expense_code,
        gps_result=gps_result,
        result=result,
        receipt_image_url=receipt_image_url,
        employee_name=profile.employee_name,
        department=profile.department,
        project_code=profile.project_code,
    )

    return JSONResponse(
        {
            "receipt": {
                "merchant": receipt_data.get("merchant"),
                "date": receipt_data.get("date"),
                "amount": receipt_data.get("amount"),
                "vat": receipt_data.get("vat"),
                "ocr_engine": receipt_data.get("ocr_engine"),
            },
            "expense_code": expense_code,
            "gps": gps_result,
            "result": result,
            "expense_item_id": item.id,
            "transaction_id": trans.id,
            "receipt_image_url": receipt_image_url,
        }
    )


@app.post("/api/receipts/gps-retry")
async def gps_retry(req: GpsRetryRequest):
    normalized = normalize_emp_no(req.emp_no)
    gps_logs = await daou_service.get_attendance_gps(normalized, req.receipt_date or "")
    if gps_logs:
        return {
            "gps": {
                "score": 80,
                "grade": "GREEN",
                "details": ["GPS 출근 기록 확인됨"],
                "mode": "ATTENDANCE_RETRY",
            },
            "result": {"status": "RETRY_READY"},
        }
    return {
        "gps": {
            "score": 25,
            "grade": "RED",
            "details": ["GPS 출근 기록 없음"],
            "mode": "ATTENDANCE_RETRY",
        },
        "result": {"status": "REJECTED"},
    }


@app.post("/api/receipts/exempt-submit")
async def exempt_submit(req: ExemptSubmitRequest):
    await daou_service.send_notification(
        normalize_emp_no(req.emp_no),
        f"📋 GPS 면제 검토 요청\n"
        f"직원: {normalize_emp_no(req.emp_no)}\n"
        f"가맹점: {(req.receipt or {}).get('merchant', '-')}\n"
        f"금액: {int((req.receipt or {}).get('amount') or 0):,}원\n"
        f"사유: {req.exempt_reason}",
    )
    return {"status": "submitted", "message": "담당자 검토 요청이 전송되었습니다."}


@app.get("/api/receipts/history")
async def get_receipt_history(
    emp_no: Optional[str] = Query(None),
    admin_view: bool = Query(False),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(ExpenseItem).filter(ExpenseItem.source_type == "RECEIPT")
    normalized = normalize_emp_no(emp_no or "")
    if not admin_view:
        if not normalized:
            raise HTTPException(400, "emp_no가 필요합니다.")
        query = query.filter(ExpenseItem.emp_no == normalized)

    items = query.order_by(ExpenseItem.created_at.desc()).limit(limit).all()
    serialized = []
    total_amount = 0
    green_count = review_count = red_count = 0

    for item in items:
        total_amount += item.amount or 0
        if item.gps_grade == "GREEN":
            green_count += 1
        elif item.gps_grade == "RED":
            red_count += 1
        if item.status in {"NEEDS_REVIEW", "REJECTED"}:
            review_count += 1
        serialized.append(
            {
                "id": item.id,
                "emp_no": item.emp_no,
                "employee_name": item.employee_name,
                "department": item.department,
                "project_code": item.project_code,
                "txn_date": item.txn_date.isoformat() if item.txn_date else None,
                "merchant": item.merchant,
                "amount": item.amount,
                "vat": item.vat,
                "usage_type": item.usage_type,
                "usage_detail": item.usage_detail,
                "gps_grade": item.gps_grade,
                "gps_score": item.gps_score,
                "status": item.status,
                "evidence_url": item.evidence_url,
                "file_exists": receipt_file_exists(item.evidence_url),
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "source_ref": item.source_ref,
            }
        )

    return {
        "items": serialized,
        "summary": {
            "count": len(serialized),
            "total_amount": total_amount,
            "green_count": green_count,
            "review_count": review_count,
            "red_count": red_count,
        },
    }


async def _process_by_grade(emp_no: str, receipt: dict, expense_code: dict, gps_result: dict):
    grade = gps_result.get("grade")
    if grade == "GREEN":
        approval = await daou_service.create_expense_approval(receipt, emp_no, expense_code, gps_result)
        if approval.get("status") in {"created", "skipped"}:
            await daou_service.send_notification(
                emp_no,
                f"✅ 경비 처리 완료\n"
                f"💰 {int(receipt.get('amount') or 0):,}원 | {receipt.get('merchant', '')}\n"
                f"📍 GPS {gps_result.get('score', 0)}점",
                link_url=approval.get("redirect_url"),
            )
            return {"status": "AUTO_APPROVED", "approval": approval}
        return {"status": "NEEDS_REVIEW", "approval": approval}

    if grade == "YELLOW":
        await daou_service.send_notification(
            emp_no,
            f"⚠️ 경비 검토 필요\n"
            f"GPS 점수: {gps_result.get('score', 0)}점\n"
            f"가맹점: {receipt.get('merchant', '')}",
        )
        return {"status": "NEEDS_REVIEW"}

    await daou_service.send_notification(
        emp_no,
        f"❌ 경비 처리 불가\n"
        f"GPS 점수: {gps_result.get('score', 0)}점\n"
        f"다우 출근 GPS 확인 후 재시도해주세요.",
        link_url="daouoffice://attendance/checkin",
    )
    return {"status": "REJECTED"}


@app.post("/api/transactions")
async def fetch_transactions(query: TransactionQuery, db: Session = Depends(get_db)):
    try:
        adapter = get_adapter(query.card_company)
        transactions = await adapter.fetch_transactions(
            query.corp_id,
            query.card_numbers,
            query.from_date,
            query.to_date,
        )
        save_summary = {"imported": 0, "skipped": 0, "expense_items": 0}
        if query.save_to_db:
            save_summary = await persist_card_transactions(db, query, transactions)

        return {
            "card_company": query.card_company,
            "count": len(transactions),
            "save_summary": save_summary,
            "transactions": [
                {
                    "merchant": t.merchant,
                    "trans_date": t.trans_date.isoformat(),
                    "trans_time": t.trans_time,
                    "amount": t.amount,
                    "vat": t.vat,
                    "mcc_code": t.mcc_code,
                    "approval_no": t.approval_no,
                    "card_number_masked": t.card_number_masked,
                }
                for t in transactions
            ],
        }
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/api/daou/callback")
async def daou_callback(payload: CallbackPayload, db: Session = Depends(get_db)):
    logger.info("결재 콜백 수신: docId=%s, status=%s", payload.docId, payload.status)
    log = db.query(ApprovalLog).filter(ApprovalLog.daou_doc_id == payload.docId).first()
    if log:
        log.status = payload.status or log.status
        log.callback_data = payload.model_dump()
        log.updated_at = datetime.now()
        if log.transaction_id:
            transaction = db.query(Transaction).filter(Transaction.id == log.transaction_id).first()
            if transaction:
                transaction.daou_approval_status = payload.status or transaction.daou_approval_status
                expense_item = db.query(ExpenseItem).filter(ExpenseItem.transaction_id == transaction.id).first()
                if expense_item and payload.status:
                    expense_item.status = payload.status
        db.commit()
    return {"status": "OK"}


@app.get("/api/merchant-mappings")
async def get_merchant_mappings(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(MerchantMapping)
    if search:
        query = query.filter(MerchantMapping.merchant_pattern.ilike(f"%{search}%"))
    mappings = query.order_by(MerchantMapping.use_count.desc(), MerchantMapping.id.desc()).limit(200).all()
    return [
        {
            "id": m.id,
            "merchant_pattern": m.merchant_pattern,
            "mcc_code": m.mcc_code,
            "expense_code": m.expense_code,
            "expense_name": m.expense_name,
            "source": m.source,
            "confidence": m.confidence,
            "use_count": m.use_count,
        }
        for m in mappings
    ]


@app.post("/api/merchant-mappings")
async def create_merchant_mapping(payload: MerchantMappingRequest, db: Session = Depends(get_db)):
    ensure_expense_codes_seeded(db)
    existing = db.query(MerchantMapping).filter(MerchantMapping.merchant_pattern == payload.merchant_pattern.strip()).first()
    if existing:
        existing.expense_code = payload.expense_code
        existing.expense_name = payload.expense_name
        existing.mcc_code = payload.mcc_code
        existing.source = "MANUAL"
        existing.confidence = 1.0
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "status": "updated"}

    mapping = MerchantMapping(
        merchant_pattern=payload.merchant_pattern.strip(),
        expense_code=payload.expense_code,
        expense_name=payload.expense_name,
        mcc_code=payload.mcc_code,
        source="MANUAL",
        confidence=1.0,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return {"id": mapping.id, "status": "created"}


@app.put("/api/merchant-mappings/{mapping_id}")
async def update_merchant_mapping(mapping_id: int, payload: MerchantMappingRequest, db: Session = Depends(get_db)):
    mapping = db.query(MerchantMapping).filter(MerchantMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(404, "매핑을 찾을 수 없습니다.")
    mapping.merchant_pattern = payload.merchant_pattern.strip()
    mapping.expense_code = payload.expense_code
    mapping.expense_name = payload.expense_name
    mapping.mcc_code = payload.mcc_code
    mapping.source = "MANUAL"
    mapping.confidence = 1.0
    db.commit()
    db.refresh(mapping)
    return {"id": mapping.id, "status": "updated"}


@app.delete("/api/merchant-mappings/{mapping_id}")
async def delete_merchant_mapping(mapping_id: int, db: Session = Depends(get_db)):
    mapping = db.query(MerchantMapping).filter(MerchantMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(404, "매핑을 찾을 수 없습니다.")
    db.delete(mapping)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/dashboard/stats")
async def get_dashboard_stats(emp_no: Optional[str] = Query(None), db: Session = Depends(get_db)):
    current_month = datetime.now().replace(day=1).date()
    query = db.query(
        Transaction.daou_approval_status,
        func.count(Transaction.id).label("count"),
        func.sum(Transaction.amount).label("total_amount"),
    ).filter(Transaction.trans_date >= current_month)

    normalized = normalize_emp_no(emp_no or "")
    if normalized:
        query = query.filter(Transaction.emp_no == normalized)

    stats = query.group_by(Transaction.daou_approval_status).all()

    gps_query = db.query(
        func.count(ExpenseItem.id).label("count"),
        func.sum(func.case((ExpenseItem.gps_grade == "GREEN", 1), else_=0)).label("green_count"),
    ).filter(
        ExpenseItem.source_type == "RECEIPT",
        ExpenseItem.txn_date >= current_month,
    )
    if normalized:
        gps_query = gps_query.filter(ExpenseItem.emp_no == normalized)
    gps_stat = gps_query.first()
    gps_rate = 0
    if gps_stat and (gps_stat.count or 0) > 0:
        gps_rate = round(((gps_stat.green_count or 0) / gps_stat.count) * 100)

    return {
        "month": current_month.strftime("%Y-%m"),
        "gps_rate": gps_rate,
        "by_status": [
            {
                "status": row.daou_approval_status or "PENDING",
                "count": row.count,
                "total_amount": row.total_amount or 0,
            }
            for row in stats
        ],
    }
