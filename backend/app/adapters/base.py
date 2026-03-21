"""
ARM Platform - BaseCardAdapter
카드사 어댑터 공통 추상 클래스 및 정규화 스키마
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class NormalizedTransaction:
    """카드사별 거래 데이터를 공통 스키마로 정규화"""
    card_company: str                    # WOORI, SHINHAN, SAMSUNG, CODEF
    card_number_masked: str              # **** **** **** 1234
    trans_date: date
    trans_time: str                      # HH:MM
    merchant: str                        # 가맹점명
    merchant_category: str              # 카테고리
    mcc_code: str                        # MCC 코드
    amount: int                          # 결제금액 (원)
    vat: int                             # 부가세
    installment: int                     # 할부개월 (0=일시불)
    approval_no: str                     # 승인번호
    daou_form_type: str = "CORP_CARD_EXPENSE"
    lat: Optional[float] = None          # 가맹점 위도
    lng: Optional[float] = None          # 가맹점 경도
    raw_data: dict = field(default_factory=dict)


class BaseCardAdapter(ABC):
    """모든 카드사 어댑터가 상속받는 추상 클래스"""

    @abstractmethod
    async def authenticate(self) -> str:
        """OAuth2 또는 API Key 기반 인증 → access_token 반환"""
        pass

    @abstractmethod
    async def fetch_transactions(
        self,
        corp_id: str,
        card_numbers: List[str],
        from_date: date,
        to_date: date
    ) -> List[NormalizedTransaction]:
        """법인카드 거래내역 조회 → NormalizedTransaction 리스트 반환"""
        pass

    @abstractmethod
    async def fetch_cards(self, corp_id: str) -> List[dict]:
        """법인카드 목록 조회"""
        pass
