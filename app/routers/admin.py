from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import httpx
import uuid

from app.database import get_db
from app.config import settings
from app.models.medicine import ActiveIngredient
from app.models.interaction import FoodItem, SupplementIngredient, InteractionRule

router = APIRouter(prefix="/admin", tags=["admin"])

DUR_BASE_URL = "http://apis.data.go.kr/1471000/DURPrdlstInfoService03"


async def _fetch_page(client: httpx.AsyncClient, page: int, num_rows: int = 100) -> dict:
    params = {
        "serviceKey": settings.dur_api_key,
        "pageNo": page,
        "numOfRows": num_rows,
        "type": "json",
    }
    resp = await client.get(f"{DUR_BASE_URL}/getUsjntTabooInfoList03", params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


async def _get_or_create_ingredient(db: AsyncSession, code: str, name_ko: str) -> ActiveIngredient:
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


async def _process_page(db: AsyncSession, items: list) -> int:
    added = 0
    for item in items:
        ingr_code = item.get("INGR_CODE", "")
        ingr_name = item.get("INGR_NAME", "") or item.get("INGR_KOR_NAME", "")
        mix_code = item.get("MIXTURE_INGR", "") or item.get("MIXTURE_INGR_CODE", "")
        mix_name = item.get("MIXTURE_INGR_KOR_NAME", "") or item.get("MIXTURE_INGR_NAME", "") or mix_code
        reason = item.get("PROHBT_CONTENT", "") or item.get("REMARK", "")

        if not (ingr_code and mix_code):
            continue

        subject = await _get_or_create_ingredient(db, ingr_code, ingr_name)
        obj = await _get_or_create_ingredient(db, mix_code, mix_name)

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


@router.post("/sync-dur")
async def sync_dur(db: AsyncSession = Depends(get_db)):
    if not settings.dur_api_key:
        raise HTTPException(status_code=400, detail="DUR_API_KEY가 설정되지 않았습니다.")

    added = 0
    total_fetched = 0

    async with httpx.AsyncClient() as client:
        # 1페이지로 전체 건수 파악
        first = await _fetch_page(client, 1, num_rows=50)
        body = first.get("body", {})
        total = int(body.get("totalCount", 0))
        pages = (total + 49) // 50

        items = body.get("items", [])
        if isinstance(items, dict):
            items = [items]
        total_fetched += len(items)
        added += await _process_page(db, items)

        # 나머지 페이지: 페이지마다 처리 후 즉시 커밋
        for page in range(2, pages + 1):
            data = await _fetch_page(client, page, num_rows=50)
            items = data.get("body", {}).get("items", [])
            if isinstance(items, dict):
                items = [items]
            elif not isinstance(items, list):
                items = []
            total_fetched += len(items)
            added += await _process_page(db, items)

    return {"message": f"DUR 병용금기 {added}건 저장 완료", "total_fetched": total_fetched}


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    return {
        "ingredients": (await db.execute(select(func.count(ActiveIngredient.id)))).scalar(),
        "food_items": (await db.execute(select(func.count(FoodItem.id)))).scalar(),
        "supplements": (await db.execute(select(func.count(SupplementIngredient.id)))).scalar(),
        "interaction_rules": (await db.execute(select(func.count(InteractionRule.id)))).scalar(),
    }
