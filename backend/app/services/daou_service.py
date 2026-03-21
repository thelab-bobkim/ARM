"""
ARM Platform - DaouOffice Service
다우오피스 OpenAPI v4 연동
- 전자결재 자동 기안 (POST /public/v4/approval/document)
- 알림 발송 (POST /public/v1/noti)
- 출퇴근 GPS 조회 (GET /public/v1/attendance/gps-logs)
"""
import httpx
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class DaouOfficeService:
    BASE_URL = "https://api.daouoffice.com"
    APPROVAL_URL = f"{BASE_URL}/public/v4/approval/document"
    APPROVAL_POPUP_URL = f"{BASE_URL}/public/v4/approval/document/popup"
    NOTI_URL = f"{BASE_URL}/public/v1/noti"
    GPS_URL = f"{BASE_URL}/public/v1/attendance/gps-logs"
    WORKS_URL = f"{BASE_URL}/public/v1/works"

    def __init__(self, client_id: str, client_secret: str, callback_base_url: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.callback_base_url = callback_base_url

    # ─────────────────────────────────────────
    # 전자결재 자동 기안
    # ─────────────────────────────────────────
    async def create_expense_approval(
        self,
        receipt: dict,
        emp_no: str,
        expense_code: dict,
        gps_result: dict,
        use_popup: bool = False
    ) -> dict:
        """
        영수증 데이터 → 다우오피스 전자결재 기안 생성
        Returns: {"status": "created", "redirect_url": "...", "doc_id": "..."}
        """
        content_html = self._build_expense_html(receipt, expense_code, gps_result)
        title = (
            f"[경비청구] {receipt.get('merchant', '가맹점')} "
            f"{receipt.get('amount', 0):,}원 ({receipt.get('date', '')})"
        )

        form_data = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "productName": "ARM-경비관리플랫폼",
            "productVersion": "2.0",
            "clientCompanyName": "ARM Platform",
            "formCode": expense_code.get("code", "CORP_CARD_EXPENSE"),
            "title": title,
            "draftEmpNo": emp_no,
            "content": content_html,
            "callbackUrl": f"{self.callback_base_url}/api/daou/callback",
            "partnerDocId": receipt.get("approval_no", ""),
        }

        url = self.APPROVAL_POPUP_URL if use_popup else self.APPROVAL_URL

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    data=form_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    follow_redirects=False
                )
                redirect_url = resp.headers.get("location", "")
                return {
                    "status": "created",
                    "redirect_url": redirect_url,
                    "http_status": resp.status_code
                }
        except Exception as e:
            logger.error(f"전자결재 기안 생성 실패: {e}")
            return {"status": "error", "error": str(e)}

    def _build_expense_html(self, receipt: dict, expense_code: dict, gps_result: dict) -> str:
        """전자결재 본문 HTML 생성 (data-id 태그 포함)"""
        gps_badge = {
            "GREEN": "🟢 자동승인",
            "YELLOW": "🟡 검토필요",
            "RED": "🔴 반려"
        }.get(gps_result.get("grade", ""), "")

        rows = [
            ("merchant",      "가맹점명",      receipt.get("merchant", "")),
            ("trans_date",    "거래일",        receipt.get("date", "")),
            ("trans_time",    "거래시간",      receipt.get("time", "")),
            ("amount",        "금액",          f"{receipt.get('amount', 0):,}원"),
            ("vat",           "부가세",        f"{receipt.get('vat', 0):,}원"),
            ("expense_code",  "경비코드",      f"{expense_code.get('code', '')} ({expense_code.get('name', '')})"),
            ("expense_source","분류방법",      expense_code.get("source", "")),
            ("gps_score",     "GPS 검증점수",  f"{gps_result.get('score', 0)}점 {gps_badge}"),
            ("gps_details",   "검증 상세",     ", ".join(gps_result.get("details", []))),
        ]

        html = """<table border="1" style="width:100%;border-collapse:collapse;font-size:13px;">
  <thead>
    <tr style="background:#1a56db;color:#fff;">
      <th style="padding:8px;width:30%;">항목</th>
      <th style="padding:8px;">내용</th>
    </tr>
  </thead>
  <tbody>"""
        for data_id, label, value in rows:
            html += f"""
    <tr>
      <td style="padding:7px 10px;background:#f8fafc;font-weight:bold;">{label}</td>
      <td data-id="{data_id}" style="padding:7px 10px;">{value}</td>
    </tr>"""
        html += "\n  </tbody>\n</table>"
        return html

    # ─────────────────────────────────────────
    # 알림 발송
    # ─────────────────────────────────────────
    async def send_notification(
        self,
        emp_no: str,
        message: str,
        link_url: Optional[str] = None,
        mail_title: Optional[str] = None
    ) -> dict:
        """다우오피스 메신저 알림 발송 (월 1,500건 무료)"""
        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "productName": "ARM-경비관리플랫폼",
            "receivers": [emp_no],
            "message": message
        }
        if link_url:
            payload["linkUrl"] = link_url
        if mail_title:
            payload["mailTitle"] = mail_title
            payload["mailMessage"] = message

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self.NOTI_URL, json=payload)
                return resp.json()
        except Exception as e:
            logger.error(f"알림 발송 실패 (emp: {emp_no}): {e}")
            return {"error": str(e)}

    async def send_bulk_notification(self, emp_nos: List[str], message: str) -> dict:
        """다수 직원에게 동시 알림 발송"""
        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "productName": "ARM-경비관리플랫폼",
            "receivers": emp_nos,
            "message": message
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self.NOTI_URL, json=payload)
            return resp.json()

    # ─────────────────────────────────────────
    # 출퇴근 GPS 조회
    # ─────────────────────────────────────────
    async def get_attendance_gps(self, emp_no: str, target_date: str) -> List[dict]:
        """
        특정 직원의 특정 날짜 GPS 출퇴근 기록 조회
        Returns: [{timestamp, lat, lng, type}]
        """
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.GPS_URL,
                    params={
                        "clientId": self.client_id,
                        "clientSecret": self.client_secret,
                        "empNo": emp_no,
                        "date": target_date.replace("-", "")
                    }
                )
                data = resp.json()
                return data.get("gpsLogs", [])
        except Exception as e:
            logger.warning(f"GPS 조회 실패 (emp: {emp_no}, date: {target_date}): {e}")
            return []

    async def check_gps_today(self, emp_no: str) -> bool:
        """오늘 GPS 출근 체크 여부 확인"""
        from datetime import date
        today = date.today().isoformat()
        logs = await self.get_attendance_gps(emp_no, today)
        return len(logs) > 0
