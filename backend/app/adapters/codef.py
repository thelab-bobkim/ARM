"""
ARM Platform - CODEFAdapter
CODEF API 연동 어댑터 (우리,신한,삼성,현대,롯데,KB,하나,농협 등 14개사 통합)
API: https://api.codef.io
"""
import httpx
import base64
import json
from datetime import date
from typing import List
from .base import BaseCardAdapter, NormalizedTransaction

CODEF_COMPANY_MAP = {
    "SHINHAN": "0301",
    "SAMSUNG": "0381",
    "HYUNDAI": "0371",
    "LOTTE": "0361",
    "KB": "0311",
    "HANA": "0391",
    "NONGHYUP": "0071",
    "BC": "0321",
}


class CODEFAdapter(BaseCardAdapter):
    TOKEN_URL = "https://oauth.codef.io/oauth/token"
    BASE_URL = "https://api.codef.io"
    APPROVAL_ENDPOINT = "/v1/kr/card/b/account/approval-list"

    def __init__(self, client_id: str, client_secret: str, company_code: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.company_code = company_code
        self._token: str = None

    async def authenticate(self) -> str:
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.TOKEN_URL,
                data={"grant_type": "client_credentials", "scope": "read"},
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            resp.raise_for_status()
            self._token = resp.json().get("access_token")
            return self._token

    async def fetch_transactions(
        self,
        corp_id: str,
        card_numbers: List[str],
        from_date: date,
        to_date: date
    ) -> List[NormalizedTransaction]:
        token = await self.authenticate()
        results = []
        for card_no in card_numbers:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.BASE_URL}{self.APPROVAL_ENDPOINT}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "organization": self.company_code,
                        "loginType": "2",          # 법인카드
                        "cardNo": card_no,
                        "startDate": from_date.strftime("%Y%m%d"),
                        "endDate": to_date.strftime("%Y%m%d"),
                        "orderBy": "0",
                        "inquiryType": "0"
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for t in data.get("data", []):
                        results.append(self._normalize(t, card_no))
        return results

    async def fetch_cards(self, corp_id: str) -> List[dict]:
        return []  # CODEF는 카드목록 별도 조회 미지원, 직접 입력 필요

    def _normalize(self, raw: dict, card_no: str) -> NormalizedTransaction:
        masked = ("*" * 12 + card_no[-4:]) if len(card_no) >= 4 else card_no
        company_name = {v: k for k, v in CODEF_COMPANY_MAP.items()}.get(self.company_code, "UNKNOWN")
        return NormalizedTransaction(
            card_company=company_name,
            card_number_masked=masked,
            trans_date=date(
                int(raw.get("usedDate", "20000101")[:4]),
                int(raw.get("usedDate", "20000101")[4:6]),
                int(raw.get("usedDate", "20000101")[6:8])
            ),
            trans_time=raw.get("usedTime", "00:00"),
            merchant=raw.get("storeName", ""),
            merchant_category=raw.get("storeCategory", ""),
            mcc_code=raw.get("mcc", "0000"),
            amount=int(str(raw.get("usedAmount", "0")).replace(",", "")),
            vat=int(str(raw.get("vatAmount", "0")).replace(",", "")),
            installment=int(raw.get("installmentMonth", "0") or 0),
            approval_no=raw.get("approvalNo", ""),
            raw_data=raw
        )
