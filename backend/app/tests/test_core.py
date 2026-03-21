"""
ARM Platform - 테스트 스위트
핵심 서비스 단위 테스트
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


# ─────────────────────────────────────────
# GPS 검증 엔진 테스트
# ─────────────────────────────────────────
class TestGPSValidationEngine:
    def setup_method(self):
        from app.services.gps_validation import GPSValidationEngine
        self.engine = GPSValidationEngine()

    def test_green_grade_close_location(self):
        """같은 위치, 같은 시간 → GREEN (100점)"""
        receipt = {
            "date": "2026-03-21", "time": "12:30",
            "amount": 15000, "category": "식비",
            "lat": 37.5665, "lng": 126.9780
        }
        gps_logs = [{"timestamp": "2026-03-21T12:00:00", "lat": 37.5665, "lng": 126.9780}]
        result = self.engine.calculate_trust_score(receipt, gps_logs)
        assert result["grade"] == "GREEN"
        assert result["score"] >= 80

    def test_red_grade_no_gps(self):
        """GPS 로그 없음 → RED"""
        receipt = {"date": "2026-03-21", "time": "12:30", "amount": 15000}
        result = self.engine.calculate_trust_score(receipt, [])
        assert result["grade"] == "RED"
        assert result["score"] < 50

    def test_distance_deduction(self):
        """8.7km 거리 (>5km) → 50점 감점 → 점수 50점 이하"""
        receipt = {
            "date": "2026-03-21", "time": "12:00",
            "lat": 37.5665, "lng": 126.9780
        }
        gps_logs = [{"timestamp": "2026-03-21T12:00:00", "lat": 37.6200, "lng": 127.0500}]
        result = self.engine.calculate_trust_score(receipt, gps_logs)
        # 8.7km > 5km → -50점, 최종 점수 50점 이하 또는 grade RED/YELLOW
        assert result["score"] <= 55 or result["grade"] in ("RED", "YELLOW")

    def test_haversine_distance(self):
        """Haversine 거리 계산 정확도 테스트"""
        # 서울 시청 → 서울역 (약 1.2km)
        dist = self.engine._haversine(37.5662, 126.9779, 37.5546, 126.9707)
        assert 1000 < dist < 1500, f"예상 거리 1.2km, 실제: {dist:.0f}m"


# ─────────────────────────────────────────
# 경비 코드 매핑 테스트
# ─────────────────────────────────────────
class TestExpenseCodeMappingService:
    def setup_method(self):
        from app.services.expense_mapping import ExpenseCodeMappingService
        self.service = ExpenseCodeMappingService()

    @pytest.mark.asyncio
    async def test_mcc_mapping_food(self):
        """MCC 5812 → 식대 매핑"""
        result = await self.service.get_expense_code("어느식당", "5812")
        assert result["code"] == "MEAL_EXP"
        assert result["source"] == "MCC_MAPPING"

    @pytest.mark.asyncio
    async def test_keyword_mapping_starbucks(self):
        """스타벅스 → 식대 키워드 매핑"""
        result = await self.service.get_expense_code("스타벅스강남역점", "")
        assert result["code"] == "MEAL_EXP"
        assert result["source"] == "KEYWORD_MAP"

    @pytest.mark.asyncio
    async def test_fuel_mcc_mapping(self):
        """MCC 5541 → 주유비 매핑"""
        result = await self.service.get_expense_code("GS주유소", "5541")
        assert result["code"] == "TRANS_FUEL"


# ─────────────────────────────────────────
# OCR 서비스 텍스트 파싱 테스트
# ─────────────────────────────────────────
class TestOCRService:
    def setup_method(self):
        from app.services.ocr_service import OCRService
        self.service = OCRService()

    def test_parse_receipt_with_amount(self):
        """금액 포함 영수증 텍스트 파싱"""
        text = """스타벅스 강남점
2026.03.21
아메리카노
합계: 5,500원
부가세: 500원"""
        result = self.service._parse_receipt_text(text)
        assert result["amount"] == 5500
        assert result["vat"] == 500
        assert "스타벅스" in result.get("merchant", "")

    def test_parse_date(self):
        """날짜 파싱"""
        text = "거래일시: 2026년 03월 21일 14:30"
        result = self.service._parse_receipt_text(text)
        assert result.get("date") == "2026-03-21"
        assert result.get("time") == "14:30"

    def test_parse_amount_with_comma(self):
        """쉼표 포함 금액 파싱"""
        text = "총 결제금액 35,000원"
        result = self.service._parse_receipt_text(text)
        assert result["amount"] == 35000


# ─────────────────────────────────────────
# WooriCardAdapter 정규화 테스트
# ─────────────────────────────────────────
class TestWooriCardAdapter:
    def setup_method(self):
        from app.adapters.woori import WooriCardAdapter
        self.adapter = WooriCardAdapter("test_id", "test_secret", use_test=True)

    def test_normalize_transaction(self):
        """우리카드 거래 데이터 정규화"""
        raw = {
            "card_no": "1234567890123456",
            "trans_date": "20260321",
            "trans_time": "14:30",
            "merchant_name": "스타벅스 강남점",
            "merchant_category": "카페",
            "mcc": "5812",
            "amount": "5500",
            "vat": "500",
            "installment": "0",
            "approval_no": "AP12345678"
        }
        result = self.adapter._normalize(raw)
        assert result.card_company == "WOORI"
        assert result.amount == 5500
        assert result.mcc_code == "5812"
        assert result.trans_date == date(2026, 3, 21)
        assert "3456" in result.card_number_masked
