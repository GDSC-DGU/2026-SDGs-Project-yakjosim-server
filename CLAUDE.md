# 약조심 (YakJosim) — 약물·음식·영양제 상호작용 안내 서비스

## 프로젝트 개요

약 이름, 처방전 사진, 영양제, 음식을 입력하면 해당 조합의 위험 여부를 분석하고,
일반인이 이해할 수 있는 언어로 복용 주의사항을 안내하는 FastAPI 백엔드 서비스.

- **서비스 유형**: 의료 진단이 아닌 복약 안전 정보 안내 서비스 (AI 답변은 반드시 데이터 근거와 함께 제공)
- **개발 단계**: 프로토타입 (MVP). 과도한 추상화나 미사용 기능 추가 금지.

---

## 기술 스택

| 레이어 | 기술 | 비고 |
|--------|------|------|
| 백엔드 | FastAPI (Python 3.11+) | 비동기, 자동 문서화 |
| ORM | SQLAlchemy 2.x + Alembic | async 모드 |
| DB | PostgreSQL | Railway 플러그인 |
| LLM | Claude API (claude-haiku-4-5) | 상호작용 자연어 설명 |
| OCR | Naver CLOVA OCR | 처방전/약봉투 텍스트 추출 |
| 외부 데이터 | 식약처 DUR 공공 OpenAPI | 병용금기, 상호작용 룰 |
| 배포 | Railway | railway.toml로 구성 |
| 의존성 관리 | uv (권장) 또는 pip + requirements.txt | |

---

## 프로토타입 MVP 범위

### 포함 기능 (구현)

1. **약 이름 검색** — 제품명 입력 → 제품명/성분명 검색 결과 반환
2. **약물-약물 상호작용 분석** — 여러 약 성분 조합의 병용금기/주의 분석 (DUR API 기반)
3. **약물-음식 상호작용 분석** — 자몽, 커피, 알코올 등 대표 음식군과의 상호작용
4. **약물-영양제 상호작용 분석** — 철분, 칼슘, 비타민K 등 주요 성분
5. **처방전 OCR** — CLOVA OCR로 이미지에서 약 이름 후보 추출
6. **AI 자연어 설명** — Claude API로 상호작용 결과를 쉬운 문장으로 변환

### 제외 기능 (프로토타입 이후)

- 회원가입/로그인, 복용 목록 저장, 결과 공유(PDF), 복용 간격 알림
- 관리자 콘솔, 외부 API 자동 동기화 배치
- 개인 건강정보 기반 위험도 보정

---

## 프로젝트 디렉토리 구조

```
sdgs/
├── app/
│   ├── main.py              # FastAPI 앱 진입점
│   ├── config.py            # 환경변수, 설정
│   ├── database.py          # DB 연결, 세션
│   ├── models/              # SQLAlchemy 모델
│   │   ├── medicine.py
│   │   ├── interaction.py
│   │   └── session.py
│   ├── schemas/             # Pydantic 스키마 (요청/응답)
│   ├── routers/             # 라우터 (엔드포인트 그룹)
│   │   ├── medicines.py     # GET /medicines/search
│   │   ├── interactions.py  # POST /interactions/analyze
│   │   └── ocr.py           # POST /ocr/prescription
│   ├── services/            # 비즈니스 로직
│   │   ├── dur_api.py       # DUR 공공 API 클라이언트
│   │   ├── ocr_service.py   # CLOVA OCR 연동
│   │   ├── llm_service.py   # Claude API 연동
│   │   └── analyzer.py      # 상호작용 분석 오케스트레이터
│   └── data/
│       └── seeds/           # 음식/영양제 초기 데이터 (JSON)
├── migrations/              # Alembic 마이그레이션
├── tests/
├── .env.example
├── requirements.txt
├── railway.toml
└── CLAUDE.md
```

---

## 데이터베이스 스키마 (프로토타입용 간소화)

> 원본 plans.md의 12개 테이블에서 프로토타입 MVP에 필요한 핵심 5개 테이블로 축소.

### medicine_products
```sql
id            UUID PRIMARY KEY
product_name  VARCHAR(255) NOT NULL
manufacturer  VARCHAR(255)
item_seq      VARCHAR(50)          -- 식약처 품목기준코드
dosage_form   VARCHAR(50)
source        VARCHAR(50)
```

### active_ingredients
```sql
id                  UUID PRIMARY KEY
ingredient_name_ko  VARCHAR(255) NOT NULL
ingredient_name_en  VARCHAR(255)
ingredient_code     VARCHAR(50)
```

### product_ingredients (N:M 연결)
```sql
id             UUID PRIMARY KEY
product_id     UUID REFERENCES medicine_products(id)
ingredient_id  UUID REFERENCES active_ingredients(id)
amount         DECIMAL
unit           VARCHAR(20)
is_main        BOOLEAN DEFAULT TRUE
```

### food_items
```sql
id              UUID PRIMARY KEY
food_name       VARCHAR(100) NOT NULL
food_group      VARCHAR(50)           -- grapefruit, dairy, caffeine, alcohol 등
aliases         JSONB                 -- 유사어 목록 ["자몽", "자몽주스"]
```

### supplement_ingredients
```sql
id        UUID PRIMARY KEY
name_ko   VARCHAR(100) NOT NULL
name_en   VARCHAR(100)
category  VARCHAR(50)              -- vitamin, mineral, omega 등
aliases   JSONB
```

### interaction_rules
```sql
id                  UUID PRIMARY KEY
subject_type        VARCHAR(20)  -- drug | food | supplement
subject_id          UUID
object_type         VARCHAR(20)
object_id           UUID
interaction_type    VARCHAR(50)  -- contraindication | caution | absorption_decrease | effect_increase | effect_decrease
severity            VARCHAR(20)  -- critical | high | medium | low
mechanism           TEXT
recommendation      TEXT
min_interval_hours  INT
evidence_source     VARCHAR(100)
is_active           BOOLEAN DEFAULT TRUE
```

> **주의**: DUR API에서 수집한 데이터는 `interaction_rules`에 정규화하여 저장.
> DUR API 원문은 별도 캐시 없이 주기적 동기화 스크립트로 처리 (프로토타입 단계에서는 수동 실행).

---

## 핵심 API 엔드포인트

### GET /api/v1/medicines/search
약 제품명 검색 (자동완성용)

```
Query: keyword=타이레놀
Response: { results: [{ productId, productName, manufacturer, ingredients[] }] }
```

### POST /api/v1/interactions/analyze
상호작용 분석 (메인 기능)

```json
Request:
{
  "items": [
    { "type": "drug", "productId": "uuid" },
    { "type": "food", "foodId": "uuid" },
    { "type": "supplement", "supplementIngredientId": "uuid" }
  ]
}

Response:
{
  "overallSeverity": "high",
  "results": [
    {
      "severity": "high",
      "combination": ["아세트아미노펜", "알코올"],
      "interactionType": "effect_increase",
      "summary": "...",
      "explanation": "...",  // Claude API 생성
      "recommendation": "...",
      "source": "DUR / 약학정보원"
    }
  ]
}
```

### POST /api/v1/ocr/prescription
처방전/약봉투 이미지 업로드 → 약 이름 후보 추출

```
Request: multipart/form-data (file, documentType)
Response: { documentId, ocrConfidence, extractedItems[] }
```

---

## 외부 API 연동

### 식약처 DUR 공공 OpenAPI
- 포털: https://www.data.go.kr/data/15059486/openapi.do
- 제공 정보: 병용금기, 연령금기, 임부금기, 용량주의
- 연동 방식: HTTP GET, XML/JSON 응답
- 환경변수: `DUR_API_KEY`

### Naver CLOVA OCR
- 환경변수: `CLOVA_OCR_URL`, `CLOVA_OCR_SECRET`
- JPG, PNG, HEIC, PDF 지원
- 한국어 처방전 텍스트 인식에 최적화

### Claude API
- 환경변수: `ANTHROPIC_API_KEY`
- 모델: `claude-haiku-4-5` (비용 효율)
- 용도: 상호작용 분석 결과의 자연어 설명 생성
- **규칙**: 근거 데이터 없이 임의 답변 생성 금지. 항상 `interaction_rules` 데이터를 컨텍스트로 주입.

---

## 환경변수 (.env)

```env
# DB
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/yakjosim

# 외부 API
DUR_API_KEY=
CLOVA_OCR_URL=
CLOVA_OCR_SECRET=
ANTHROPIC_API_KEY=

# 앱 설정
ENVIRONMENT=development  # development | production
LOG_LEVEL=INFO
```

---

## 개발 명령어

```bash
# 의존성 설치
pip install -r requirements.txt

# DB 마이그레이션
alembic upgrade head

# 개발 서버 실행
uvicorn app.main:app --reload --port 8000

# API 문서 확인
open http://localhost:8000/docs

# 테스트
pytest tests/
```

---

## Railway 배포

### railway.toml
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
```

### Railway 설정 순서
1. `railway new` 또는 Railway 대시보드에서 프로젝트 생성
2. GitHub 저장소 연결 (또는 `railway up`으로 직접 배포)
3. **Plugins** 탭에서 PostgreSQL 추가 → `DATABASE_URL` 자동 주입
4. **Variables** 탭에서 나머지 환경변수 수동 추가 (`DUR_API_KEY`, `CLOVA_OCR_URL` 등)
5. 배포 시 `railway.toml`의 `startCommand`가 마이그레이션 → 서버 시작 순서로 실행됨

> `$PORT`는 Railway가 자동으로 주입하는 환경변수. `--port 8000`으로 고정하지 말 것.

---

## 개발 규칙

- **추측 금지**: 불명확한 요구사항은 구현 전 반드시 확인
- **MVP 원칙**: 명세에 없는 기능 추가 금지. 현재 필요하지 않은 추상화 금지
- **에러 처리**: 외부 API(DUR, CLOVA, Claude) 실패 시 명확한 에러 메시지 반환. 사일런트 실패 금지
- **AI 안전**: Claude API 응답에 반드시 근거 데이터(`interaction_rules`)를 포함. 데이터 없으면 `"확인된 정보 없음"` 반환
- **의료 면책**: 모든 API 응답에 `disclaimer` 필드 포함 ("본 정보는 참고용이며 의사·약사와 상담하세요")
