"""
ARM Platform - WooriCardAdapter
우리카드 OpenAPI 연동 어댑터
API: https://openapi.wooricard.com:8443
"""
import httpx
from datetime import date
from typing import List
from .base import BaseCardAdapter, NormalizedTransaction


class WooriCardAdapter(BaseCardAdapter):
    BASE_URL = "https://openapi.wooricard.com:8443"
    TEST_URL = "https://dopenapi.wooricard.com:8443"
    TOKEN_ENDPOINT = "/oauth/v1/token"
    APPROVAL_ENDPOINT = "/api/v1/cards/approvals"
    CARDS_ENDPOINT = "/api/v1/cards/info"

    def __init__(self, client_id: str, client_secret: str, use_test: bool = False):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base = self.TEST_URL if use_test else self.BASE_URL
        self._token: str = None

    async def authenticate(self) -> str:
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(
                f"{self.base}{self.TOKEN_ENDPOINT}",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "card"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
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
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(
                f"{self.base}{self.APPROVAL_ENDPOINT}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "corp_id": corp_id,
                    "card_numbers": card_numbers,
                    "from_date": from_date.strftime("%Y%m%d"),
                    "to_date": to_date.strftime("%Y%m%d"),
                    "page_no": 1,
                    "page_size": 100
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return [self._normalize(t) for t in data.get("transactions", [])]

    async def fetch_cards(self, corp_id: str) -> List[dict]:
        token = await self.authenticate()
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.get(
                f"{self.base}{self.CARDS_ENDPOINT}",
                headers={"Authorization": f"Bearer {token}"},
                params={"corp_id": corp_id}
            )
            resp.raise_for_status()
            return resp.json().get("cards", [])

    def _normalize(self, raw: dict) -> NormalizedTransaction:
        card_no = raw.get("card_no", "")
        masked = ("*" * 12 + card_no[-4:]) if len(card_no) >= 4 else card_no
        return NormalizedTransaction(
            card_company="WOORI",
            card_number_masked=masked,
            trans_date=date(
                int(raw.get("trans_date", "20000101")[:4]),
                int(raw.get("trans_date", "20000101")[4:6]),
                int(raw.get("trans_date", "20000101")[6:8])
            ),
            trans_time=raw.get("trans_time", "00:00"),
            merchant=raw.get("merchant_name", ""),
            merchant_category=raw.get("merchant_category", ""),
            mcc_code=raw.get("mcc", "0000"),
            amount=int(raw.get("amount", 0)),
            vat=int(raw.get("vat", 0)),
            installment=int(raw.get("installment", 0)),
            approval_no=raw.get("approval_no", ""),
            raw_data=raw
        )
