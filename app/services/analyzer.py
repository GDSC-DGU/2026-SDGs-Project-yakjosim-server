from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.medicine import ActiveIngredient, ProductIngredient
from app.models.interaction import FoodItem, SupplementIngredient, InteractionRule
from app.schemas.interaction import AnalysisItem, InteractionResult
from app.services.llm_service import explain_interaction

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}


async def analyze_interactions(items: list[AnalysisItem], db: AsyncSession) -> list[InteractionResult]:
    id_name: dict[str, str] = {}   # entity_id -> 표시명
    all_ids: list[str] = []

    for item in items:
        if item.type == "drug" and item.productId:
            # 제품 → 성분 ID 변환 (interaction_rules는 성분 단위로 저장됨)
            rows = await db.execute(
                select(ActiveIngredient.id, ActiveIngredient.ingredient_name_ko)
                .join(ProductIngredient, ActiveIngredient.id == ProductIngredient.ingredient_id)
                .where(ProductIngredient.product_id == item.productId)
            )
            for ingr_id, ingr_name in rows.all():
                id_name[ingr_id] = ingr_name
                all_ids.append(ingr_id)

        elif item.type == "food" and item.foodId:
            row = (await db.execute(
                select(FoodItem).where(FoodItem.id == item.foodId)
            )).scalar_one_or_none()
            if row:
                id_name[row.id] = row.food_name
                all_ids.append(row.id)

        elif item.type == "supplement" and item.supplementIngredientId:
            row = (await db.execute(
                select(SupplementIngredient).where(SupplementIngredient.id == item.supplementIngredientId)
            )).scalar_one_or_none()
            if row:
                id_name[row.id] = row.name_ko
                all_ids.append(row.id)

    if not all_ids:
        return []

    rules = (await db.execute(
        select(InteractionRule).where(
            InteractionRule.is_active == True,
            InteractionRule.subject_id.in_(all_ids),
            InteractionRule.object_id.in_(all_ids),
        )
    )).scalars().all()

    results = []
    for rule in rules:
        subject_name = id_name.get(rule.subject_id, rule.subject_id)
        object_name = id_name.get(rule.object_id, rule.object_id)
        explanation = await explain_interaction({
            "combination": [subject_name, object_name],
            "interaction_type": rule.interaction_type,
            "mechanism": rule.mechanism or "",
            "recommendation": rule.recommendation or "",
        })
        results.append(InteractionResult(
            severity=rule.severity,
            combination=[subject_name, object_name],
            interactionType=rule.interaction_type,
            summary=rule.mechanism or "상호작용이 확인되었습니다.",
            explanation=explanation,
            recommendation=rule.recommendation or "의사·약사와 상담하세요.",
            source=rule.evidence_source or "DUR 데이터",
        ))

    return sorted(results, key=lambda r: SEVERITY_ORDER.get(r.severity, 0), reverse=True)
