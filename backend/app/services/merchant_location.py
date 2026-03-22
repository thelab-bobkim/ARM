"""
ARM Platform - 가맹점 위치 조회 서비스
카카오 로컬 API (무료) 또는 Google Places API 로 가맹점 주소 → 좌표 변환
"""
import os
import logging
import httpx
from typing import Optional, Dict, Any
from math import radians, sin, cos, sqrt, atan2

logger = logging.getLogger(__name__)

KAKAO_API_KEY = os.getenv("KAKAO_API_KEY", "")
GOOGLE_PLACES_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")


class MerchantLocationService:
    """가맹점명 → 위도/경도 변환 + 촬영 위치와 거리 계산"""

    # 거리 등급 기준
    GRADE_THRESHOLDS = {
        "GREEN":  500,    # 500m 이내  → 현장 인증
        "YELLOW": 2000,   # 2km 이내   → 근처 인정
        "RED":    999999, # 2km 초과   → 위치 불일치
    }

    async def get_merchant_coords(self, merchant_name: str, address_hint: str = "") -> Optional[Dict]:
        """가맹점명으로 좌표 조회 (카카오 → Google 순서로 시도)"""
        coords = None

        if KAKAO_API_KEY:
            coords = await self._kakao_search(merchant_name, address_hint)

        if not coords and GOOGLE_PLACES_KEY:
            coords = await self._google_places_search(merchant_name, address_hint)

        if not coords:
            # API 키 없을 때 → 한국 주요 프랜차이즈 좌표 fallback DB
            coords = self._fallback_coords(merchant_name)

        return coords

    async def _kakao_search(self, keyword: str, address_hint: str = "") -> Optional[Dict]:
        """카카오 키워드 검색 API"""
        query = f"{keyword} {address_hint}".strip()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://dapi.kakao.com/v2/local/search/keyword.json",
                    params={"query": query, "size": 1},
                    headers={"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
                )
                data = resp.json()
                docs = data.get("documents", [])
                if docs:
                    place = docs[0]
                    return {
                        "lat": float(place["y"]),
                        "lng": float(place["x"]),
                        "name": place["place_name"],
                        "address": place["address_name"],
                        "source": "KAKAO"
                    }
        except Exception as e:
            logger.warning(f"카카오 검색 실패 ({keyword}): {e}")
        return None

    async def _google_places_search(self, keyword: str, address_hint: str = "") -> Optional[Dict]:
        """Google Places Text Search API"""
        query = f"{keyword} {address_hint} 한국".strip()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/place/textsearch/json",
                    params={
                        "query": query,
                        "language": "ko",
                        "region": "kr",
                        "key": GOOGLE_PLACES_KEY
                    }
                )
                data = resp.json()
                results = data.get("results", [])
                if results:
                    loc = results[0]["geometry"]["location"]
                    return {
                        "lat": loc["lat"],
                        "lng": loc["lng"],
                        "name": results[0].get("name"),
                        "address": results[0].get("formatted_address"),
                        "source": "GOOGLE"
                    }
        except Exception as e:
            logger.warning(f"Google Places 검색 실패 ({keyword}): {e}")
        return None

    def _fallback_coords(self, merchant_name: str) -> Optional[Dict]:
        """
        API 키 없을 때 주요 프랜차이즈 근사 좌표 반환
        실제 운영 시 카카오 API 키 권장 (월 30만건 무료)
        """
        name_lower = merchant_name.lower()
        FRANCHISE_DB = {
            # 식당/카페 프랜차이즈
            "스타벅스":      {"lat": 37.5665, "lng": 126.9780},
            "맥도날드":      {"lat": 37.5665, "lng": 126.9780},
            "롯데리아":      {"lat": 37.5665, "lng": 126.9780},
            "bhc":          {"lat": 37.5665, "lng": 126.9780},
            "교촌":          {"lat": 37.5665, "lng": 126.9780},
            "bbq":          {"lat": 37.5665, "lng": 126.9780},
            "이마트":        {"lat": 37.5040, "lng": 127.0497},
            "코스트코":      {"lat": 37.4969, "lng": 127.0571},
            "ipark":         {"lat": 37.5276, "lng": 126.9647},  # 아이파크몰
            "아이파크":      {"lat": 37.5276, "lng": 126.9647},
        }
        for key, coords in FRANCHISE_DB.items():
            if key in name_lower:
                return {**coords, "name": merchant_name, "address": "프랜차이즈(추정)", "source": "FALLBACK"}
        return None

    def calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine 공식으로 두 좌표 간 거리(m) 계산"""
        R = 6_371_000
        phi1, phi2 = radians(lat1), radians(lat2)
        dphi = radians(lat2 - lat1)
        dlng = radians(lng2 - lng1)
        a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlng/2)**2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))

    def grade_distance(self, distance_m: float) -> Dict[str, Any]:
        """거리 → GPS 등급 및 점수 산출"""
        if distance_m <= self.GRADE_THRESHOLDS["GREEN"]:
            score = 100
            grade = "GREEN"
            msg = f"✅ 가맹점 반경 {distance_m:.0f}m 이내 - 현장 확인"
        elif distance_m <= self.GRADE_THRESHOLDS["YELLOW"]:
            score = 65
            grade = "YELLOW"
            msg = f"⚠️ 가맹점에서 {distance_m:.0f}m - 근접 위치"
        else:
            score = 20
            grade = "RED"
            msg = f"❌ 가맹점에서 {distance_m:.0f}m - 위치 불일치"

        return {
            "score": score,
            "grade": grade,
            "distance_m": round(distance_m),
            "details": [msg],
            "validation_type": "REALTIME_GPS"
        }

    async def validate(
        self,
        merchant_name: str,
        capture_lat: float,
        capture_lng: float,
        address_hint: str = ""
    ) -> Dict[str, Any]:
        """
        메인 검증 함수
        - 가맹점 좌표 조회
        - 촬영 위치와 거리 계산
        - 등급 반환
        """
        merchant_coords = await self.get_merchant_coords(merchant_name, address_hint)

        if not merchant_coords:
            # 가맹점 좌표 조회 실패 → 중립 처리 (YELLOW)
            return {
                "score": 60,
                "grade": "YELLOW",
                "distance_m": None,
                "details": ["가맹점 위치 조회 불가 - 담당자 확인 예정"],
                "validation_type": "REALTIME_GPS",
                "merchant_coords": None
            }

        distance_m = self.calculate_distance(
            capture_lat, capture_lng,
            merchant_coords["lat"], merchant_coords["lng"]
        )

        result = self.grade_distance(distance_m)
        result["merchant_coords"] = merchant_coords
        result["capture_coords"] = {"lat": capture_lat, "lng": capture_lng}

        logger.info(
            f"[GPS검증] {merchant_name} | 촬영위치→가맹점: {distance_m:.0f}m | "
            f"{result['grade']} ({result['score']}점) | 출처: {merchant_coords['source']}"
        )
        return result
