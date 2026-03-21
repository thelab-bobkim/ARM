"""
ARM Platform - GPS Validation Engine
다우오피스 GPS 출퇴근 기록 ↔ 영수증 위치/시간 교차 검증
신뢰도 점수(0~100) 및 GREEN/YELLOW/RED 등급 산출
"""
import logging
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime, date
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class GPSValidationEngine:
    """
    영수증 거래 위치·시간 vs 다우오피스 GPS 출퇴근 기록 교차검증
    """

    # 점수 감점 기준
    DEDUCT_DISTANCE = {5000: 50, 2000: 30, 500: 10}   # 거리(m): 감점
    DEDUCT_TIME = {120: 30, 30: 10}                     # 시간차(분): 감점

    def calculate_trust_score(
        self,
        receipt: Dict[str, Any],
        gps_logs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Args:
            receipt: OCR 결과 {date, time, amount, merchant, lat, lng, category}
            gps_logs: [{timestamp, lat, lng, type}] (다우오피스 GPS 로그)
        Returns:
            {score, grade, details, closest_gps, distance_m, time_diff_min}
        """
        if not gps_logs:
            return {
                "score": 25, "grade": "RED",
                "details": ["GPS 출근 기록 없음"],
                "distance_m": None, "time_diff_min": None
            }

        score = 100
        details = []

        # 영수증 날짜·시간 파싱
        receipt_dt = self._parse_receipt_datetime(receipt)

        # 가장 가까운 GPS 기록 탐색
        closest = self._find_closest_gps(receipt_dt, gps_logs)
        if not closest:
            return {"score": 30, "grade": "RED", "details": ["유효한 GPS 기록 없음"]}

        # 1. 거리 검증
        distance_m = None
        if receipt.get("lat") and receipt.get("lng"):
            distance_m = self._haversine(
                receipt["lat"], receipt["lng"],
                closest.get("lat", 0), closest.get("lng", 0)
            )
            for threshold, deduct in sorted(self.DEDUCT_DISTANCE.items(), reverse=True):
                if distance_m > threshold:
                    score -= deduct
                    details.append(f"위치 불일치: 거리 {distance_m:.0f}m")
                    break
        else:
            # 위치 정보 없으면 중간 점수 유지
            score -= 5
            details.append("영수증 위치 정보 없음")

        # 2. 시간 차이 검증
        time_diff_min = abs(
            (datetime.fromisoformat(closest["timestamp"]) - receipt_dt).total_seconds() / 60
        )
        for threshold, deduct in sorted(self.DEDUCT_TIME.items(), reverse=True):
            if time_diff_min > threshold:
                score -= deduct
                details.append(f"시간 불일치: {time_diff_min:.0f}분 차이")
                break

        # 3. 공휴일/주말 여부
        if self._is_holiday(receipt_dt.date()):
            score -= 10
            details.append("공휴일/주말 거래")

        # 4. 야간 주류 구매 패턴
        if self._is_late_night_alcohol(receipt_dt, receipt.get("category", "")):
            score -= 15
            details.append("야간 주류 거래 의심")

        # 5. 금액 이상치 (카테고리 평균 3배 초과)
        category_avg = receipt.get("category_avg", 0)
        if category_avg and receipt.get("amount", 0) > category_avg * 3:
            score -= 10
            details.append(f"금액 이상치: {receipt['amount']:,}원 (평균 대비 3배 초과)")

        score = max(0, score)
        grade = "GREEN" if score >= 80 else ("YELLOW" if score >= 50 else "RED")

        return {
            "score": score,
            "grade": grade,
            "details": details if details else ["정상 처리"],
            "closest_gps": closest,
            "distance_m": distance_m,
            "time_diff_min": round(time_diff_min, 1) if time_diff_min else None
        }

    def _parse_receipt_datetime(self, receipt: dict) -> datetime:
        """영수증 날짜+시간 → datetime"""
        date_str = receipt.get("date", "")
        time_str = receipt.get("time", "12:00")
        try:
            return datetime.fromisoformat(f"{date_str}T{time_str}")
        except Exception:
            return datetime.now()

    def _find_closest_gps(self, receipt_dt: datetime, gps_logs: list) -> Optional[dict]:
        """영수증 시간과 가장 가까운 GPS 로그 반환"""
        try:
            return min(
                gps_logs,
                key=lambda g: abs(
                    (datetime.fromisoformat(g["timestamp"]) - receipt_dt).total_seconds()
                )
            )
        except Exception:
            return None

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """두 좌표 간 거리(m) 계산 - Haversine 공식"""
        R = 6_371_000  # 지구 반지름 (m)
        phi1, phi2 = radians(lat1), radians(lat2)
        dphi = radians(lat2 - lat1)
        dlambda = radians(lon2 - lon1)
        a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))

    def _is_holiday(self, d: date) -> bool:
        """공휴일/주말 여부"""
        if d.weekday() >= 5:  # 토(5), 일(6)
            return True
        try:
            import holidays
            return d in holidays.KR(years=d.year)
        except ImportError:
            return False

    def _is_late_night_alcohol(self, dt: datetime, category: str) -> bool:
        """야간(23시 이후) 주류 관련 거래 여부"""
        is_night = dt.hour >= 23 or dt.hour < 2
        alcohol_keywords = ["주류", "bar", "술", "맥주", "소주", "와인", "포차"]
        category_lower = category.lower()
        return is_night and any(k in category_lower for k in alcohol_keywords)
