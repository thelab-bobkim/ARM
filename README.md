# ARM Platform - 경비 자동청구 시스템 v2.0

> 다우오피스 메신저 연동 법인카드 경비 자동처리 플랫폼

## 📋 프로젝트 개요

영수증 사진 1장 업로드 → OCR 처리 → 경비코드 자동 매핑 → GPS 교차검증 → 다우오피스 전자결재 자동 기안

**서버**: AWS Lightsail `13.125.110.156`  
**저장소**: https://github.com/thelab-bobkim/ARM

---

## 🏗️ 프로젝트 구조

```
ARM/
├── backend/
│   ├── app/
│   │   ├── adapters/          # 카드사 어댑터 (Woori, CODEF)
│   │   ├── services/          # 핵심 서비스 (OCR, GPS, 경비코드, 다우오피스)
│   │   ├── routers/           # FastAPI 라우터
│   │   ├── models/            # SQLAlchemy ORM 모델
│   │   ├── utils/             # DB 설정 등 유틸
│   │   ├── tests/             # pytest 테스트
│   │   ├── main.py            # FastAPI 앱 진입점
│   │   └── scheduler.py       # APScheduler 월간 알림
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/        # React 컴포넌트
│   │   └── App.jsx            # 메인 앱
│   ├── package.json
│   └── Dockerfile
├── database/
│   └── init.sql               # PostgreSQL 초기화 SQL
├── nginx/
│   └── nginx.conf             # Nginx 리버스 프록시 설정
├── .github/workflows/
│   └── deploy.yml             # GitHub Actions CI/CD
├── scripts/
│   └── server_setup.sh        # Lightsail 서버 최초 설정
├── docker-compose.prod.yml    # 프로덕션 Docker Compose
└── .env.example               # 환경변수 템플릿
```

---

## ⚡ 빠른 시작

### 1. 서버 최초 설정 (Lightsail)
```bash
# SSH 접속
ssh ubuntu@13.125.110.156

# 설정 스크립트 실행
git clone https://github.com/thelab-bobkim/ARM
cd ARM
chmod +x scripts/server_setup.sh
sudo ./scripts/server_setup.sh
```

### 2. 환경변수 설정
```bash
cp .env.example .env.prod
nano .env.prod  # API 키 입력
```

### 3. 서비스 시작
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 4. 헬스체크
```bash
curl http://localhost:8000/health
```

---

## 🔑 API 키 발급 순서

| 서비스 | URL | 소요 기간 |
|--------|-----|----------|
| 다우오피스 OpenAPI | 고객포털 내 신청 | 1~3일 |
| 우리카드 OpenAPI | https://apiportal.wooricard.com | 2~3일 |
| CODEF API | https://developer.codef.io | 1~2일 |
| Google Vision API | https://console.cloud.google.com | 즉시 |
| OpenAI API | https://platform.openai.com | 즉시 |

---

## 🧪 테스트 실행

```bash
cd backend
pip install -r requirements.txt
pytest app/tests/ -v --cov=app
```

---

## 📡 주요 API 엔드포인트

| Method | URL | 설명 |
|--------|-----|------|
| POST | /api/receipts/upload | 영수증 업로드 → 전체 자동 처리 |
| POST | /api/transactions | 카드사 거래내역 조회 |
| POST | /api/daou/callback | 다우오피스 결재 콜백 |
| GET  | /api/expense-codes | 경비코드 목록 |
| GET  | /api/merchant-mappings | 가맹점 매핑 목록 |
| POST | /api/merchant-mappings | 가맹점 매핑 추가 |
| GET  | /api/dashboard/stats | 월간 통계 |
| GET  | /health | 서비스 헬스체크 |

---

## 🔄 처리 흐름 (GPS 등급별)

```
영수증 업로드
    │
    ├─ OCR (Google Vision / GPT-4o)
    │      ↓ merchant, amount, date, lat/lng
    ├─ 경비코드 매핑 (DB → MCC → AI)
    │      ↓ expense_code, name, confidence
    ├─ GPS 교차검증 (다우오피스 API)
    │      ↓ score(0-100), grade
    │
    ├─ GREEN (80+) → 자동 전자결재 기안 → D+1 정산
    ├─ YELLOW (50-79) → 담당자 검토 알림
    └─ RED (<50) → 반려 + GPS 체크 유도 메시지
```

---

## 📅 월간 알림 스케줄

| 날짜 | 알림 |
|------|------|
| 매월 1일 09:00 | 경비 접수 시작 공지 |
| 매일 09:05 | GPS 미체크 직원 알림 |
| 15일 09:00 | 중간 점검 (D-13) |
| 23일 09:00 | 마감 D-7 |
| 25일 09:00 | 마감 D-5 |
| 27일 09:00 | 마감 D-3 |
| 28일 09:00 | 마감 당일 최종 알림 |
| 28일 17:00 | 접수 마감 처리 |

---

## 💰 비용 (월간)

| 항목 | 비용 |
|------|------|
| AWS Lightsail (4GB) | ₩13,000 |
| Google Vision API (≤1,000건) | 무료 |
| GPT-4o Vision 폴백 | ~₩3,000 |
| 다우오피스 OpenAPI | 무료 |
| **합계** | **~₩16,000** |

---

## 🔒 보안

- 카드번호 뒷 4자리만 저장 (PCI-DSS)
- JWT 기반 API 인증
- HTTPS (Let's Encrypt)
- 모든 시크릿은 환경변수에만 저장
- Lightsail 방화벽: 80, 443, 22 포트만 개방
