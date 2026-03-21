"""
ARM Platform - AdapterFactory
카드사 코드로 적절한 어댑터를 생성하는 팩토리
"""
import os
from .woori import WooriCardAdapter
from .codef import CODEFAdapter, CODEF_COMPANY_MAP
from .base import BaseCardAdapter


def get_adapter(card_company: str) -> BaseCardAdapter:
    """
    카드사 코드 → 어댑터 인스턴스 반환
    사용: adapter = get_adapter("WOORI")
    """
    company = card_company.upper()

    if company == "WOORI":
        return WooriCardAdapter(
            client_id=os.getenv("WOORI_CLIENT_ID", ""),
            client_secret=os.getenv("WOORI_CLIENT_SECRET", ""),
            use_test=os.getenv("ENV", "production") != "production"
        )

    elif company in CODEF_COMPANY_MAP:
        return CODEFAdapter(
            client_id=os.getenv("CODEF_CLIENT_ID", ""),
            client_secret=os.getenv("CODEF_CLIENT_SECRET", ""),
            company_code=CODEF_COMPANY_MAP[company]
        )

    else:
        raise ValueError(f"지원하지 않는 카드사입니다: {card_company}")
