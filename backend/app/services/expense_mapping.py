"""
ARM Platform - Expense Code Mapping Service
MCC 코드 → 다우오피스 경비 코드 3단계 매핑 시스템
1단계: DB 가맹점 매핑 테이블
2단계: MCC 코드 직접 매핑
3단계: GPT-4o AI 자동 분류
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# MCC 코드 → 경비 코드 매핑 (국제 표준 기준)
MCC_TO_EXPENSE = {
    # 식대
    "5812": ("MEAL_EXP",       "식대"),
    "5813": ("MEAL_EXP",       "식대"),
    "5814": ("MEAL_EXP",       "식대"),
    "5411": ("MEAL_EXP",       "식료품"),
    # 교통
    "4111": ("TRANS_LOCAL",    "대중교통"),
    "4112": ("TRANS_TRAIN",    "기차/KTX"),
    "4511": ("TRANS_AIR",      "항공"),
    "4121": ("TRANS_TAXI",     "택시"),
    "4131": ("TRANS_BUS",      "버스"),
    "5541": ("TRANS_FUEL",     "주유비"),
    "5542": ("TRANS_FUEL",     "주유비"),
    "7523": ("TRANS_PARKING",  "주차비"),
    # 숙박
    "7011": ("LODGING_EXP",    "숙박비"),
    "7012": ("LODGING_EXP",    "숙박비"),
    # 사무용품
    "5943": ("OFFICE_SUPPLY",  "사무용품"),
    "5111": ("OFFICE_SUPPLY",  "사무용품"),
    # IT/소프트웨어
    "7372": ("SW_SERVICE",     "소프트웨어/서비스"),
    "5045": ("EQUIP_PURCHASE", "장비구매"),
    "5734": ("EQUIP_PURCHASE", "전자장비"),
    # 통신
    "4813": ("COMM_EXP",       "통신비"),
    "4814": ("COMM_EXP",       "통신비"),
    # 의료
    "8011": ("MEDICAL_EXP",    "의료비"),
    "8099": ("MEDICAL_EXP",    "의료비"),
    # 교육
    "8220": ("EDU_EXP",        "교육비"),
    "8299": ("EDU_EXP",        "교육비"),
    # 복지/문화
    "7832": ("WELFARE_EXP",    "문화/복지"),
    "7941": ("WELFARE_EXP",    "문화/복지"),
}

# 가맹점명 키워드 → 경비 코드 사전 매핑
MERCHANT_KEYWORD_MAP = {
    "스타벅스": ("MEAL_EXP", "식대"),
    "커피빈": ("MEAL_EXP", "식대"),
    "이디야": ("MEAL_EXP", "식대"),
    "GS칼텍스": ("TRANS_FUEL", "주유비"),
    "SK에너지": ("TRANS_FUEL", "주유비"),
    "현대오일뱅크": ("TRANS_FUEL", "주유비"),
    "KTX": ("TRANS_TRAIN", "기차/KTX"),
    "SRT": ("TRANS_TRAIN", "기차/KTX"),
    "대한항공": ("TRANS_AIR", "항공"),
    "아시아나": ("TRANS_AIR", "항공"),
    "제주항공": ("TRANS_AIR", "항공"),
    "카카오택시": ("TRANS_TAXI", "택시"),
    "우버": ("TRANS_TAXI", "택시"),
    "교보문고": ("OFFICE_SUPPLY", "도서/사무용품"),
    "예스24": ("OFFICE_SUPPLY", "도서/사무용품"),
}


class ExpenseCodeMappingService:
    """
    영수증 가맹점 + MCC 코드 → 다우오피스 경비 코드 자동 매핑
    """

    async def get_expense_code(
        self,
        merchant: str,
        mcc_code: str,
        db=None
    ) -> dict:
        """
        3단계 매핑으로 경비 코드 결정
        Returns: {code, name, source, confidence}
        """
        # 1단계: DB 가맹점 매핑 테이블 조회
        if db:
            db_result = await self._lookup_db(merchant, db)
            if db_result:
                return db_result

        # 2단계: 키워드 기반 매핑
        keyword_result = self._lookup_keyword(merchant)
        if keyword_result:
            return keyword_result

        # 3단계: MCC 코드 매핑
        mcc_result = self._lookup_mcc(mcc_code)
        if mcc_result:
            return mcc_result

        # 4단계: GPT-4o AI 분류
        return await self._ai_classify(merchant, mcc_code, db)

    async def _lookup_db(self, merchant: str, db) -> Optional[dict]:
        """DB merchant_mappings 테이블 조회"""
        try:
            from sqlalchemy import text
            result = db.execute(
                text("SELECT expense_code, expense_name FROM merchant_mappings "
                     "WHERE :merchant ILIKE '%' || merchant_pattern || '%' "
                     "ORDER BY use_count DESC LIMIT 1"),
                {"merchant": merchant}
            ).fetchone()
            if result:
                return {
                    "code": result[0],
                    "name": result[1],
                    "source": "DB_MAPPING",
                    "confidence": 1.0
                }
        except Exception as e:
            logger.warning(f"DB 조회 오류: {e}")
        return None

    def _lookup_keyword(self, merchant: str) -> Optional[dict]:
        """키워드 사전 매핑"""
        for keyword, (code, name) in MERCHANT_KEYWORD_MAP.items():
            if keyword in merchant:
                return {"code": code, "name": name, "source": "KEYWORD_MAP", "confidence": 0.95}
        return None

    def _lookup_mcc(self, mcc_code: str) -> Optional[dict]:
        """MCC 코드 직접 매핑"""
        if mcc_code and mcc_code in MCC_TO_EXPENSE:
            code, name = MCC_TO_EXPENSE[mcc_code]
            return {"code": code, "name": name, "source": "MCC_MAPPING", "confidence": 0.9}
        return None

    async def _ai_classify(self, merchant: str, mcc_code: str, db=None) -> dict:
        """GPT-4o mini로 경비 코드 자동 분류"""
        try:
            import openai
            client = openai.AsyncOpenAI()
            categories = "\n".join([
                f"- {code}: {name}"
                for code, name in set(MCC_TO_EXPENSE.values())
            ])
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"""가맹점명: "{merchant}", MCC코드: "{mcc_code}"

다음 경비 코드 중 가장 적합한 것을 선택하여 JSON으로 반환:
{categories}
- OTHER_EXP: 기타경비

반환 형식: {{"code": "코드", "name": "이름", "confidence": 0.0~1.0, "reason": "선택 이유"}}
JSON만 반환하세요."""
                }],
                max_tokens=200
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)
            result["source"] = "AI_CLASSIFY"

            # 높은 신뢰도일 경우 DB 자동 저장
            if db and result.get("confidence", 0) > 0.85 and merchant:
                try:
                    from sqlalchemy import text
                    db.execute(
                        text("INSERT INTO merchant_mappings (merchant_pattern, expense_code, expense_name, source) "
                             "VALUES (:pattern, :code, :name, 'AI_AUTO') "
                             "ON CONFLICT (merchant_pattern) DO NOTHING"),
                        {"pattern": merchant, "code": result["code"], "name": result["name"]}
                    )
                    db.commit()
                except Exception:
                    pass
            return result

        except Exception as e:
            logger.error(f"AI 분류 실패: {e}")
            return {"code": "OTHER_EXP", "name": "기타경비", "source": "FALLBACK", "confidence": 0.3}
