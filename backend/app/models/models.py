"""
ARM Platform - SQLAlchemy ORM Models
PostgreSQL 테이블 정의
"""
from sqlalchemy import (
    Column, Integer, String, Date, Time, Boolean, Float,
    ForeignKey, JSON, DateTime, Text, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    card_company = Column(String(20), nullable=False)     # WOORI, SHINHAN, SAMSUNG
    card_number_masked = Column(String(20), nullable=False)
    card_holder_name = Column(String(50))
    corp_id = Column(String(50))
    emp_no = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    transactions = relationship("Transaction", back_populates="card")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"))
    trans_date = Column(Date, nullable=False, index=True)
    trans_time = Column(String(8))
    merchant = Column(String(200))
    mcc_code = Column(String(10))
    amount = Column(Integer, nullable=False)
    vat = Column(Integer, default=0)
    installment = Column(Integer, default=0)
    approval_no = Column(String(50), unique=True)
    expense_code = Column(String(50))
    expense_name = Column(String(100))
    expense_code_source = Column(String(20))    # DB_MAPPING, MCC_MAPPING, AI_CLASSIFY, MANUAL
    daou_approval_id = Column(String(100), index=True)
    daou_approval_status = Column(String(20), default="PENDING", index=True)
    gps_score = Column(Integer)
    gps_grade = Column(String(10))              # GREEN, YELLOW, RED
    receipt_image_path = Column(String(500))
    raw_data = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    card = relationship("Card", back_populates="transactions")
    approval_logs = relationship("ApprovalLog", back_populates="transaction")


class MerchantMapping(Base):
    __tablename__ = "merchant_mappings"

    id = Column(Integer, primary_key=True, index=True)
    merchant_pattern = Column(String(200), nullable=False, unique=True)
    mcc_code = Column(String(10))
    expense_code = Column(String(50), nullable=False)
    expense_name = Column(String(100), nullable=False)
    source = Column(String(20))                 # MANUAL, AI_AUTO, MCC_PRESET
    confidence = Column(Float, default=1.0)
    use_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExpenseCode(Base):
    __tablename__ = "expense_codes"

    code = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    account_number = Column(String(20))         # 계정과목 코드
    daou_form_code = Column(String(50))         # 다우오피스 양식 코드
    is_active = Column(Boolean, default=True)


class ApprovalLog(Base):
    __tablename__ = "approval_logs"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"))
    daou_doc_id = Column(String(100), index=True)
    emp_no = Column(String(20))
    amount = Column(Integer)
    status = Column(String(20), default="PENDING")  # PENDING, APPROVED, REJECTED, WITHDRAWN
    callback_data = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    transaction = relationship("Transaction", back_populates="approval_logs")
