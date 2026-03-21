"""
ARM Platform - OCR Service
Google Vision API (1차) + GPT-4o Vision (폴백) 이중 OCR 파이프라인
"""
import re
import base64
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OCRService:
    """
    영수증 이미지 → 구조화된 데이터 추출
    1차: Google Cloud Vision API (월 1,000건 무료)
    폴백: OpenAI GPT-4o Vision (~$0.003/건)
    """

    def __init__(self):
        self._vision_client = None
        self._openai_client = None

    def _get_vision_client(self):
        if self._vision_client is None:
            try:
                from google.cloud import vision
                self._vision_client = vision.ImageAnnotatorClient()
            except Exception as e:
                logger.warning(f"Google Vision 클라이언트 초기화 실패: {e}")
        return self._vision_client

    def _get_openai_client(self):
        if self._openai_client is None:
            import openai
            self._openai_client = openai.AsyncOpenAI()
        return self._openai_client

    async def extract_receipt(self, image_bytes: bytes) -> dict:
        """
        영수증 이미지에서 핵심 정보 추출
        Returns: {merchant, date, time, amount, vat, address, category, confidence, raw_text}
        """
        # 1차: Google Vision
        try:
            result = await self._google_vision_ocr(image_bytes)
            if result.get("confidence", 0) >= 0.75 and result.get("amount", 0) > 0:
                result["ocr_engine"] = "GOOGLE_VISION"
                return result
        except Exception as e:
            logger.warning(f"Google Vision OCR 실패: {e}")

        # 폴백: GPT-4o Vision
        try:
            result = await self._gpt4o_vision_ocr(image_bytes)
            result["ocr_engine"] = "GPT4O_VISION"
            return result
        except Exception as e:
            logger.error(f"GPT-4o Vision OCR 실패: {e}")
            return {"error": str(e), "confidence": 0.0, "amount": 0}

    async def _google_vision_ocr(self, image_bytes: bytes) -> dict:
        from google.cloud import vision
        client = self._get_vision_client()
        image = vision.Image(content=image_bytes)
        response = client.text_detection(image=image)

        if response.error.message:
            raise Exception(response.error.message)

        texts = response.text_annotations
        full_text = texts[0].description if texts else ""
        return self._parse_receipt_text(full_text)

    async def _gpt4o_vision_ocr(self, image_bytes: bytes) -> dict:
        client = self._get_openai_client()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        prompt = """이 영수증 이미지에서 다음 정보를 정확히 추출하여 JSON 형식으로 반환해주세요:
{
  "merchant": "가맹점명 (상호명)",
  "date": "YYYY-MM-DD 형식",
  "time": "HH:MM 형식",
  "amount": 총금액(숫자만, 부가세 포함),
  "vat": 부가세(숫자만, 없으면 0),
  "address": "가맹점 주소 (있는 경우)",
  "category": "식비|교통비|숙박비|사무용품|통신비|의료비|기타 중 하나",
  "confidence": 0.0~1.0 (추출 신뢰도),
  "items": [{"name": "품목명", "price": 금액}]
}
JSON만 반환하고 다른 텍스트는 포함하지 마세요."""

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_image}",
                        "detail": "high"
                    }},
                    {"type": "text", "text": prompt}
                ]
            }],
            max_tokens=800
        )

        raw_content = response.choices[0].message.content.strip()
        # JSON 코드블록 제거
        if raw_content.startswith("```"):
            raw_content = re.sub(r"```(?:json)?\n?", "", raw_content).strip()

        result = json.loads(raw_content)
        result.setdefault("confidence", 0.85)
        return result

    def _parse_receipt_text(self, text: str) -> dict:
        """Google Vision 텍스트 → 구조화 데이터 파싱"""
        result = {"raw_text": text, "confidence": 0.7}

        # 금액 추출 (합계, 총금액, 결제금액 등)
        amount_patterns = [
            r'(?:합계|총금액|결제금액|승인금액|total)[\s:：]*([0-9,]+)',
            r'([0-9,]{4,})원',
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "")
                result["amount"] = int(amount_str)
                result["confidence"] = 0.8
                break

        # 날짜 추출
        date_match = re.search(
            r'(\d{4})[.\-/년]?\s*(\d{1,2})[.\-/월]?\s*(\d{1,2})', text
        )
        if date_match:
            y, m, d = date_match.groups()
            result["date"] = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

        # 시간 추출
        time_match = re.search(r'(\d{1,2})[:\-](\d{2})(?:[:\-]\d{2})?', text)
        if time_match:
            h, mi = time_match.groups()
            result["time"] = f"{h.zfill(2)}:{mi}"

        # 부가세 추출
        vat_match = re.search(r'부가(?:가치)?세[\s:：]*([0-9,]+)', text)
        if vat_match:
            result["vat"] = int(vat_match.group(1).replace(",", ""))

        # 가맹점명 (첫 번째 유효한 줄)
        lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 1]
        if lines:
            result["merchant"] = lines[0]

        result.setdefault("amount", 0)
        result.setdefault("vat", 0)
        result.setdefault("category", "기타")
        result.setdefault("merchant", "")
        result.setdefault("date", "")
        result.setdefault("time", "")
        return result
