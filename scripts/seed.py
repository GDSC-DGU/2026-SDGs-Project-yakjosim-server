"""
정적 시드 데이터 입력: food_items, supplement_ingredients
사용: python scripts/seed.py
"""
import asyncio
import json
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from app.database import SessionLocal, engine, Base
from app.models import medicine as _m, interaction as _i  # noqa: F401
from app.models.interaction import FoodItem, SupplementIngredient

SEEDS = Path(__file__).resolve().parent.parent / "app" / "data" / "seeds"


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        food_data = json.loads((SEEDS / "food_items.json").read_text(encoding="utf-8"))
        added = 0
        for item in food_data:
            exists = (await db.execute(
                select(FoodItem).where(FoodItem.food_name == item["food_name"])
            )).scalar_one_or_none()
            if not exists:
                db.add(FoodItem(id=str(uuid.uuid4()), **item))
                added += 1
        print(f"food_items: {added}건 추가")

        supp_data = json.loads((SEEDS / "supplements.json").read_text(encoding="utf-8"))
        added = 0
        for item in supp_data:
            exists = (await db.execute(
                select(SupplementIngredient).where(SupplementIngredient.name_ko == item["name_ko"])
            )).scalar_one_or_none()
            if not exists:
                db.add(SupplementIngredient(id=str(uuid.uuid4()), **item))
                added += 1
        print(f"supplement_ingredients: {added}건 추가")

        await db.commit()
        print("시드 완료")


asyncio.run(main())
