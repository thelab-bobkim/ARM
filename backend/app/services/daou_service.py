"""
ARM Platform - DaouOffice Service
다우오피스 OpenAPI 연동 서비스
"""
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class DaouOfficeService:
    def __init__(self, client_id: str, client_secret: str, callback_base_url: str = ""):
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self.callback_base_url = (callback_base_url or "").rstrip("/")
        self.base_url = os.getenv("DAOU_BASE_URL", "https://api.daouoffice.com").rstrip("/")
        self.form_code = os.getenv("DAOU_FORM_CODE", "ARM_EXPENSE")
        self.approval_url = f"{self.base_url}/public/v4/approval/document"
        self.approval_popup_url = f"{self.base_url}/public/v4/approval/document/popup"
        self.noti_url = f"{self.base_url}/public/v1/noti"
        self.gps_url = f"{self.base_url}/public/v1/attendance/gps-logs"
        self.dept_member_url = f"{self.base_url}/public/v1/dept/member"

    def validate_config(self) -> Dict:
        errors: List[str] = []
        warnings: List[str] = []
        checks: List[Dict] = []

        has_id = bool(self.client_id)
        has_secret = bool(self.client_secret)
        has_form = bool(self.form_code)
        is_official_base = "api.daouoffice.com" in self.base_url

        checks.append({"name": "client_id", "ok": has_id})
        checks.append({"name": "client_secret", "ok": has_secret})
        checks.append({"name": "form_code", "ok": has_form})
        checks.append({"name": "official_base_url", "ok": is_official_base})

        if not has_id:
            errors.append("DAOU_CLIENT_ID가 설정되지 않았습니다.")
        if not has_secret:
            errors.append("DAOU_CLIENT_SECRET이 설정되지 않았습니다.")
        if not has_form:
            errors.append("DAOU_FORM_CODE가 설정되지 않았습니다.")
        if not is_official_base:
            warnings.append("DAOU_BASE_URL이 공식 주소(api.daouoffice.com)가 아닙니다.")

        if self.callback_base_url:
            parsed = urlparse(self.callback_base_url)
            callback_ok = parsed.scheme == "https"
            checks.append({"name": "callback_https", "ok": callback_ok})
            if not callback_ok:
                warnings.append("SERVER_URL은 HTTPS 사용을 권장합니다.")
        else:
            warnings.append("SERVER_URL이 없어 콜백 URL 검증을 생략했습니다.")

        return {
            "ready": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
            "callback_url": f"{self.callback_base_url}/api/daou/callback" if self.callback_base_url else "",
            "base_url": self.base_url,
            "form_code": self.form_code,
        }

    async def create_expense_approval(
        self,
        receipt: dict,
        emp_no: str,
        expense_code: dict,
        gps_result: dict,
        use_popup: bool = False,
    ) -> dict:
        config = self.validate_config()
        if not config["ready"]:
            return {
                "status": "skipped",
                "reason": "daou_config_invalid",
                "config": config,
            }

        content_html = self._build_expense_html(receipt, expense_code, gps_result)
        title = (
            f"[경비청구] {receipt.get('merchant', '가맹점')} "
            f"{receipt.get('amount', 0):,}원 ({receipt.get('date', '')})"
        )
        partner_doc_id = receipt.get("approval_no") or f"RCT-{emp_no}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        form_data = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "productName": "ARM-경비관리플랫폼",
            "productVersion": "2.1",
            "clientCompanyName": "ARM Platform",
            "formCode": self.form_code,
            "title": title,
            "draftEmpNo": emp_no,
            "content": content_html,
            "callbackUrl": f"{self.callback_base_url}/api/daou/callback" if self.callback_base_url else "",
            "partnerDocId": partner_doc_id,
        }
        url = self.approval_popup_url if use_popup else self.approval_url

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                resp = await client.post(
                    url,
                    data=form_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                return self._parse_approval_response(resp, partner_doc_id)
        except Exception as exc:
            logger.error("전자결재 기안 생성 실패: %s", exc)
            return {"status": "error", "error": str(exc), "partner_doc_id": partner_doc_id}

    def _parse_approval_response(self, resp: httpx.Response, partner_doc_id: str) -> dict:
        redirect_url = resp.headers.get("location", "")
        text_body = resp.text[:1000] if resp.text else ""
        json_body = None
        doc_id = None
        try:
            json_body = resp.json()
            doc_id = (
                json_body.get("docId")
                or json_body.get("data", {}).get("docId")
                or json_body.get("documentId")
            )
        except Exception:
            json_body = None

        status = "created" if resp.status_code < 400 and (redirect_url or doc_id or text_body) else "error"
        return {
            "status": status,
            "redirect_url": redirect_url,
            "doc_id": doc_id,
            "partner_doc_id": partner_doc_id,
            "http_status": resp.status_code,
            "response_json": json_body,
            "response_body": text_body,
        }

    def _build_expense_html(self, receipt: dict, expense_code: dict, gps_result: dict) -> str:
        receipt_url = receipt.get("receipt_image_url") or receipt.get("evidence_url") or ""
        receipt_link = (
            f'<a href="{receipt_url}" target="_blank">영수증 보기</a>' if receipt_url else "-"
        )
        rows = [
            ("가맹점명", receipt.get("merchant", "")),
            ("거래일", receipt.get("date", "")),
            ("거래시간", receipt.get("time", "")),
            ("금액", f"{receipt.get('amount', 0):,}원"),
            ("부가세", f"{receipt.get('vat', 0):,}원"),
            ("경비코드", f"{expense_code.get('code', '')} ({expense_code.get('name', '')})"),
            ("분류방법", expense_code.get("source", "")),
            ("GPS", f"{gps_result.get('grade', '')} / {gps_result.get('score', 0)}점"),
            ("검증상세", ", ".join(gps_result.get("details", []))),
            ("증빙", receipt_link),
        ]
        body = "".join(
            f"<tr><th style='padding:8px;background:#f8fafc;text-align:left;width:180px'>{label}</th>"
            f"<td style='padding:8px'>{value}</td></tr>"
            for label, value in rows
        )
        return (
            "<div style='font-family:Arial,sans-serif'>"
            "<h2 style='margin-bottom:12px'>ARM 경비청구 자동기안</h2>"
            "<table border='1' style='width:100%;border-collapse:collapse;font-size:13px'>"
            f"{body}</table></div>"
        )

    async def send_notification(
        self,
        emp_no: str,
        message: str,
        link_url: Optional[str] = None,
        mail_title: Optional[str] = None,
    ) -> dict:
        if not self.client_id or not self.client_secret:
            return {"status": "skipped", "reason": "daou_credentials_missing"}

        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "productName": "ARM-경비관리플랫폼",
            "receivers": [emp_no],
            "message": message,
        }
        if link_url:
            payload["linkUrl"] = link_url
        if mail_title:
            payload["mailTitle"] = mail_title
            payload["mailMessage"] = message

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self.noti_url, json=payload)
                try:
                    return resp.json()
                except Exception:
                    return {"status": resp.status_code, "body": resp.text[:500]}
        except Exception as exc:
            logger.error("알림 발송 실패 (emp: %s): %s", emp_no, exc)
            return {"status": "error", "error": str(exc)}

    async def send_bulk_notification(self, emp_nos: List[str], message: str) -> dict:
        if not emp_nos:
            return {"status": "skipped", "reason": "empty_receivers"}
        if not self.client_id or not self.client_secret:
            return {"status": "skipped", "reason": "daou_credentials_missing"}

        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "productName": "ARM-경비관리플랫폼",
            "receivers": emp_nos,
            "message": message,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(self.noti_url, json=payload)
                try:
                    return resp.json()
                except Exception:
                    return {"status": resp.status_code, "body": resp.text[:500]}
        except Exception as exc:
            logger.error("대량 알림 발송 실패: %s", exc)
            return {"status": "error", "error": str(exc)}

    async def get_attendance_gps(self, emp_no: str, target_date: str) -> List[dict]:
        if not self.client_id or not self.client_secret:
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.gps_url,
                    params={
                        "clientId": self.client_id,
                        "clientSecret": self.client_secret,
                        "empNo": emp_no,
                        "date": (target_date or "").replace("-", ""),
                    },
                )
                data = resp.json()
                return data.get("gpsLogs") or data.get("data") or []
        except Exception as exc:
            logger.warning("GPS 조회 실패 (emp: %s, date: %s): %s", emp_no, target_date, exc)
            return []

    async def check_gps_today(self, emp_no: str) -> bool:
        from datetime import date

        today = date.today().isoformat()
        logs = await self.get_attendance_gps(emp_no, today)
        return len(logs) > 0

    async def fetch_employee_profile(self, identifier: str) -> Optional[Dict]:
        if not identifier or not self.client_id or not self.client_secret:
            return None

        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "productName": "ARM-경비관리플랫폼",
            "productVersion": "2.1",
            "clientCompanyName": "ARM Platform",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(self.dept_member_url, json=payload)
                data = resp.json()
                members = data.get("data") or []
        except Exception as exc:
            logger.warning("다우 직원정보 조회 실패: %s", exc)
            return None

        normalized = identifier.strip().lower()
        for member in members:
            login_id = str(member.get("loginId") or "").strip().lower()
            employee_number = str(member.get("employeeNumber") or "").strip().lower()
            if normalized in {login_id, employee_number}:
                return {
                    "emp_no": member.get("employeeNumber") or identifier,
                    "daou_login_id": member.get("loginId") or identifier,
                    "employee_name": member.get("userName") or "",
                    "department": member.get("orgName") or "",
                    "project_code": "",
                    "email": member.get("email") or "",
                    "source": "DAOU_SYNC",
                }
        return None
