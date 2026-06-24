# 💊 약조심 (YakJosim)

> 약 이름만 입력하면, 위험한 조합을 바로 알려드립니다.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Railway-4169E1?logo=postgresql&logoColor=white)](https://railway.app/)
[![Claude API](https://img.shields.io/badge/Claude-Haiku-D4A017?logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![SDG 3](https://img.shields.io/badge/SDG-3%20Good%20Health-4C9F38)](https://sdgs.un.org/goals/goal3)

약·음식·영양제 조합의 상호작용을 분석하고, 누구나 이해할 수 있는 언어로 복약 안전 정보를 안내하는 FastAPI 백엔드 서비스입니다.

---

## 🌍 SDG 3 — 건강한 삶과 웰빙

**약조심**은 UN 지속가능발전목표 3번 *"모든 연령층의 건강한 삶 보장과 웰빙 증진"* 에 기여합니다.

의약 정보 접근성의 격차를 줄이고, 일반 시민이 복약 위험을 스스로 파악할 수 있도록 돕는 것이 이 프로젝트의 핵심 목표입니다. AI와 공공 의약 데이터(식약처 DUR)를 결합해 전문가가 아니어도 안전한 복약 결정을 내릴 수 있는 도구를 제공합니다.

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| 💊 **약 이름 검색** | 제품명·성분명으로 의약품 검색 및 자동완성 |
| ⚠️ **약물-약물 상호작용** | 여러 약 성분 조합의 병용금기·주의 분석 (DUR API 기반) |
| 🍊 **약물-음식 상호작용** | 자몽·커피·알코올 등 대표 음식군과의 상호작용 확인 |
| 💊 **약물-영양제 상호작용** | 철분·칼슘·비타민K 등 주요 영양제 성분과의 상호작용 확인 |
| 📷 **처방전 OCR** | 처방전·약봉투 사진에서 약 이름 후보 자동 추출 (CLOVA OCR) |
| 🤖 **AI 자연어 설명** | Claude API로 분석 결과를 쉬운 문장으로 변환 |

---

## 🛠 기술 스택

| 레이어 | 기술 | 비고 |
|--------|------|------|
| 백엔드 | FastAPI (Python 3.11+) | 비동기, 자동 API 문서화 |
| ORM / DB | SQLAlchemy 2.x + PostgreSQL | async 모드, Railway 플러그인 |
| 마이그레이션 | Alembic | |
| LLM | Claude API (`claude-haiku-4-5`) | 자연어 설명 생성 |
| OCR | Naver CLOVA OCR | 한국어 처방전 텍스트 인식 |
| 외부 데이터 | 식약처 DUR 공공 OpenAPI | 병용금기·상호작용 룰 |
| 배포 | Railway | `railway.toml` 구성 |

---

## 🚀 빠른 시작

### 사전 조건

- Python 3.11+
- PostgreSQL (또는 Railway 계정)
- [식약처 DUR API 키](https://www.data.go.kr/data/15059486/openapi.do)
- [Naver CLOVA OCR](https://www.ncloud.com/product/aiService/ocr) 계정
- [Anthropic API 키](https://www.anthropic.com/)

### 설치

```bash
# 저장소 클론
git clone https://github.com/your-org/2026-SDGs-Project-yakjosim-server.git
cd 2026-SDGs-Project-yakjosim-server

# 의존성 설치
pip install -r requirements.txt
```

### 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열고 아래 값들을 채워주세요
```

| 변수 | 설명 |
|------|------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 (`postgresql+asyncpg://...`) |
| `DUR_API_KEY` | 식약처 공공 OpenAPI 인증키 |
| `CLOVA_OCR_URL` | Naver CLOVA OCR 엔드포인트 URL |
| `CLOVA_OCR_SECRET` | CLOVA OCR 시크릿 키 |
| `ANTHROPIC_API_KEY` | Anthropic Claude API 키 |
| `ENVIRONMENT` | `development` 또는 `production` |

### 실행

```bash
# DB 마이그레이션
alembic upgrade head

# 시드 데이터 삽입 (음식·영양제 초기 데이터)
python scripts/seed.py

# 개발 서버 실행
uvicorn app.main:app --reload --port 8000
```

서버가 실행되면 `http://localhost:8000/docs` 에서 Swagger UI로 API를 바로 테스트할 수 있습니다.

---

## 📡 API 개요

### `GET /api/v1/medicines/search` — 약 검색

```
GET /api/v1/medicines/search?keyword=타이레놀
```

```json
{
  "results": [
    {
      "productId": "uuid",
      "productName": "타이레놀정500밀리그램",
      "manufacturer": "한국얀센",
      "ingredients": [{ "name": "아세트아미노펜", "amount": "500mg" }]
    }
  ]
}
```

### `POST /api/v1/interactions/analyze` — 상호작용 분석

```json
// Request
{
  "items": [
    { "type": "drug", "productId": "uuid" },
    { "type": "food", "foodId": "uuid" }
  ]
}
```

```json
// Response
{
  "overallSeverity": "high",
  "disclaimer": "본 정보는 참고용이며 의사·약사와 상담하세요.",
  "results": [
    {
      "severity": "high",
      "combination": ["아세트아미노펜", "알코올"],
      "interactionType": "effect_increase",
      "summary": "간 독성 위험이 크게 증가합니다.",
      "explanation": "아세트아미노펜과 알코올을 함께 복용하면...",
      "recommendation": "음주 중이거나 음주 직후에는 복용을 피하세요.",
      "source": "DUR"
    }
  ]
}
```

### `POST /api/v1/ocr/prescription` — 처방전 OCR

```
POST /api/v1/ocr/prescription
Content-Type: multipart/form-data

file=<이미지 파일>  (JPG, PNG, PDF 지원)
```

```json
{
  "documentId": "uuid",
  "ocrConfidence": 0.94,
  "extractedItems": ["타이레놀", "아목시실린", "오메프라졸"]
}
```

> 전체 API 문서는 서버 실행 후 `/docs` 또는 `/redoc` 에서 확인하세요.

---

## 📁 프로젝트 구조

```
.
├── app/
│   ├── main.py              # FastAPI 앱 진입점
│   ├── config.py            # 환경변수 설정
│   ├── database.py          # DB 연결 및 세션
│   ├── models/              # SQLAlchemy 모델
│   ├── schemas/             # Pydantic 스키마 (요청/응답)
│   ├── routers/             # 엔드포인트 라우터
│   │   ├── medicines.py
│   │   ├── interactions.py
│   │   └── ocr.py
│   ├── services/            # 비즈니스 로직
│   │   ├── dur_api.py       # DUR 공공 API 클라이언트
│   │   ├── ocr_service.py   # CLOVA OCR 연동
│   │   ├── llm_service.py   # Claude API 연동
│   │   └── analyzer.py      # 상호작용 분석 오케스트레이터
│   └── data/seeds/          # 음식·영양제 초기 데이터 (JSON)
├── migrations/              # Alembic 마이그레이션
├── scripts/
│   ├── seed.py              # 시드 데이터 삽입
│   ├── sync_dur.py          # DUR 데이터 동기화
│   └── sync_products.py     # 의약품 데이터 동기화
├── .env.example
├── requirements.txt
└── railway.toml
```

---

## 🚢 Railway 배포

```bash
# Railway CLI 설치 (최초 1회)
npm install -g @railway/cli
railway login

# 프로젝트 생성 및 배포
railway new
railway up
```

1. Railway 대시보드 → **Plugins** 탭에서 PostgreSQL 추가 (`DATABASE_URL` 자동 주입)
2. **Variables** 탭에서 나머지 환경변수 입력 (`DUR_API_KEY`, `CLOVA_OCR_URL` 등)
3. 배포 시 `railway.toml`의 `startCommand`가 마이그레이션 → 서버 시작 순서로 자동 실행

```toml
# railway.toml
[deploy]
startCommand = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
```

---

## ⚠️ 면책 조항

**약조심은 의료 진단 서비스가 아닙니다.**

본 서비스가 제공하는 모든 정보는 식약처 DUR 공공 데이터를 기반으로 한 참고용 정보이며, 개인의 건강 상태·체질·복용 이력에 따라 실제 위험도는 달라질 수 있습니다.
복약 결정은 반드시 의사 또는 약사와 상담 후 내려주세요.
