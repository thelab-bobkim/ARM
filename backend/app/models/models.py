"""
ARM Platform - SQLAlchemy ORM Models
운영용 최소 핵심 스키마
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Boolean,
    Float,
    ForeignKey,
    JSON,
    DateTime,
    Text,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UserProfile(Base):
    __tablename__ = "user_profiles"

    emp_no = Column(String(50), primary_key=True, index=True)
    daou_login_id = Column(String(100), index=True)
    employee_name = Column(String(100))
    department = Column(String(200))
    project_code = Column(String(100))
    email = Column(String(200))
    source = Column(String(30), default="MANUAL")
    synced_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("card_company", "card_number_masked", name="uq_cards_company_masked"),
    )

    id = Column(Integer, primary_key=True, index=True)
    card_company = Column(String(20), nullable=False, index=True)  # WOORI, SHINHAN, ...
    card_number_masked = Column(String(32), nullable=False, index=True)
    card_holder_name = Column(String(100))
    corp_id = Column(String(100))
    emp_no = Column(String(50), index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    transactions = relationship("Transaction", back_populates="card")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=True)
    emp_no = Column(String(50), index=True)
    employee_name = Column(String(100))
    department = Column(String(200))
    project_code = Column(String(100))
    source_type = Column(String(20), default="CARD", index=True)  # CARD, RECEIPT
    source_ref = Column(String(120), unique=True, index=True)
    trans_date = Column(Date, nullable=False, index=True)
    trans_time = Column(String(8))
    merchant = Column(String(200), index=True)
    mcc_code = Column(String(10))
    amount = Column(Integer, nullable=False)
    vat = Column(Integer, default=0)
    installment = Column(Integer, default=0)
    approval_no = Column(String(100), unique=True, index=True)
    expense_code = Column(String(50))
    expense_name = Column(String(100))
    expense_code_source = Column(String(30))
    daou_approval_id = Column(String(100), index=True)
    daou_approval_status = Column(String(20), default="PENDING", index=True)
    gps_score = Column(Integer)
    gps_grade = Column(String(10), index=True)
    receipt_image_path = Column(String(500))
    raw_data = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    card = relationship("Card", back_populates="transactions")
    approval_logs = relationship("ApprovalLog", back_populates="transaction")


class MerchantMapping(Base):
    __tablename__ = "merchant_mappings"

    id = Column(Integer, primary_key=True, index=True)
    merchant_pattern = Column(String(200), nullable=False, unique=True, index=True)
    mcc_code = Column(String(10))
    expense_code = Column(String(50), nullable=False)
    expense_name = Column(String(100), nullable=False)
    source = Column(String(20), default="MANUAL")  # MANUAL, AI_AUTO, MCC_PRESET
    confidence = Column(Float, default=1.0)
    use_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExpenseCode(Base):
    __tablename__ = "expense_codes"

    code = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    account_number = Column(String(20))
    daou_form_code = Column(String(50))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExpenseItem(Base):
    __tablename__ = "expense_items"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(20), nullable=False, index=True)  # RECEIPT, CARD
    source_ref = Column(String(120), nullable=False, unique=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    emp_no = Column(String(50), nullable=False, index=True)
    employee_name = Column(String(100))
    department = Column(String(200))
    project_code = Column(String(100))
    txn_date = Column(Date, nullable=False, index=True)
    merchant = Column(String(200), index=True)
    amount = Column(Integer, nullable=False)
    vat = Column(Integer, default=0)
    payment_method = Column(String(50))
    usage_type = Column(String(100))
    usage_detail = Column(Text)
    evidence_url = Column(String(500))
    gps_grade = Column(String(10), index=True)
    gps_score = Column(Integer)
    status = Column(String(20), default="INBOX", index=True)  # INBOX, BUNDLED, SUBMITTED, APPROVED, REJECTED
    raw_data = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ApprovalLog(Base):
    __tablename__ = "approval_logs"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"))
    daou_doc_id = Column(String(100), index=True)
    emp_no = Column(String(50), index=True)
    amount = Column(Integer)
    status = Column(String(20), default="PENDING", index=True)
    callback_data = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    transaction = relationship("Transaction", back_populates="approval_logs")
