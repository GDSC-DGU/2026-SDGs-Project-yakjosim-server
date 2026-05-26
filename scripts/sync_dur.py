"""
식약처 DUR 병용금기 데이터 동기화
사용: python scripts/sync_dur.py [--probe]
  --probe: 첫 번째 항목의 필드명만 출력 (API 응답 확인용)
"""
import asyncio
import httpx
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import os
from sqlalchemy import select
from app.database import SessionLocal, engine, Base
from app.models import medicine as _m, interaction as _i  # noqa: F401
from app.models.medicine import ActiveIngredient
from app.models.interaction import InteractionRule

DUR_API_KEY = os.environ.get("DUR_API_KEY", "")
BASE_URL = "http://apis.data.go.kr/1471000/DURPrdlstInfoService03"


async def fetch_page(client: httpx.AsyncClient, endpoint: str, page: int, num_rows: int = 100) -> dict:
    params = {
        "serviceKey": DUR_API_KEY,
        "pageNo": page,
        "numOfRows": num_rows,
        "type": "json",
    }
    resp = await client.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def parse_items(data: dict) -> tuple[list[dict], int]:
    body = data.get("body", {})
    total = int(body.get("totalCount", 0))
    items = body.get("items", [])
    if isinstance(items, dict):
        items = [items]
    elif not isinstance(items, list):
        items = []
    return items, total


async def get_or_create_ingredient(db, code: str, name_ko: str) -> ActiveIngredient:
    row = (await db.execute(
        select(ActiveIngredient).where(ActiveIngredient.ingredient_code == code)
    )).scalar_one_or_none()
    if not row:
        row = ActiveIngredient(
            id=str(uuid.uuid4()),
            ingredient_name_ko=name_ko or code,
            ingredient_code=code,
        )
        db.add(row)
        await db.flush()
    return row


async def sync_contraindications(db) -> int:
    """병용금기 (getUsjntTabooInfoList03) 동기화"""
    endpoint = "getUsjntTabooInfoList03"
    async with httpx.AsyncClient() as client:
        first, total = parse_items(await fetch_page(client, endpoint, 1))
        if not first:
            print("데이터 없음 — API 키나 엔드포인트를 확인하세요.")
            return 0

        print(f"병용금기 총 {total}건 수집 시작")
        all_items = list(first)
        pages = (total + 99) // 100
        for page in range(2, pages + 1):
            items, _ = parse_items(await fetch_page(client, endpoint, page))
            all_items.extend(items)
            print(f"  페이지 {page}/{pages} 수집 완료", end="\r")

    print(f"\n총 {len(all_items)}건 파싱 중...")
    added = 0
    for item in all_items:
        # 실제 API 필드명 — 다를 경우 --probe로 확인 후 수정
        ingr_code = item.get("INGR_CODE", "")
        ingr_name = item.get("INGR_NAME", "") or item.get("INGR_KOR_NAME", "")
        mix_code = item.get("MIXTURE_INGR", "") or item.get("MIXTURE_INGR_CODE", "")
        mix_name = (item.get("MIXTURE_INGR_KOR_NAME", "")
                    or item.get("MIXTURE_INGR_NAME", "")
                    or mix_code)
        reason = item.get("PROHBT_CONTENT", "") or item.get("REMARK", "")

        if not (ingr_code and mix_code):
            continue

        subject = await get_or_create_ingredient(db, ingr_code, ingr_name)
        obj = await get_or_create_ingredient(db, mix_code, mix_name)

        exists = (await db.execute(
            select(InteractionRule).where(
                InteractionRule.subject_id == subject.id,
                InteractionRule.object_id == obj.id,
                InteractionRule.interaction_type == "contraindication",
            )
        )).scalar_one_or_none()

        if not exists:
            db.add(InteractionRule(
                id=str(uuid.uuid4()),
                subject_type="drug",
                subject_id=subject.id,
                object_type="drug",
                object_id=obj.id,
                interaction_type="contraindication",
                severity="critical",
                mechanism=reason or None,
                recommendation="이 약물 조합은 병용금기입니다. 반드시 의사·약사와 상담하세요.",
                evidence_source="식약처 DUR 병용금기",
                is_active=True,
            ))
            added += 1

    await db.commit()
    return added


async def probe():
    """API 응답 필드명 확인"""
    if not DUR_API_KEY:
        print("DUR_API_KEY가 설정되지 않았습니다.")
        return
    async with httpx.AsyncClient() as client:
        items, total = parse_items(await fetch_page(client, "getUsjntTabooInfoList03", 1, 1))
    if items:
        print(f"총 {total}건 | 첫 번째 항목 필드:")
        for k, v in items[0].items():
            print(f"  {k}: {v}")
    else:
        print("항목 없음")


async def main():
    if not DUR_API_KEY:
        print("오류: DUR_API_KEY 환경변수가 없습니다. .env 파일을 확인하세요.")
        sys.exit(1)

    if "--probe" in sys.argv:
        await probe()
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        added = await sync_contraindications(db)
        print(f"병용금기 {added}건 신규 저장 완료")


asyncio.run(main())
