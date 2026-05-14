from sqlalchemy import func, select
from src.models.aliment import Aliment

# Mapping stratégique inchangé
FOOD_MAPPING = {
    "bowl": "Oatmeal",
    "cup": "Coffee",
    "wine glass": "Red Wine",
    "bottle": "Water",
    "sandwich": "Turkey Sandwich",
    "pizza": "Pizza",
    "donut": "Chocolate Donut",
    "cake": "Cupcake",
    "broccoli": "Steamed Broccoli",
    "carrot": "Carrot Sticks",
    "apple": "Apple",
    "banana": "Banana",
    "dining table": None,
    "chair": None,
    "refrigerator": None,
    "person": None,
    "fork": None,
    "knife": None,
    "spoon": None,
}

async def enrich_with_nutrition(detections, db_session):
    final_results = []
    for item in detections:
        raw_label = item["label"].lower().strip()
        label_to_search = FOOD_MAPPING.get(raw_label, raw_label)

        if label_to_search is None:
            continue

        # Requête basée sur le schéma Infra
        query = (
            select(Aliment)
            .where(Aliment.nom.ilike(f"%{label_to_search}%"))
            .order_by(func.length(Aliment.nom))
        )
        result = await db_session.execute(query)
        aliment_data = result.scalars().first()

        if aliment_data:
            item.update(
                {
                    "id_aliment": aliment_data.id_aliment, # Champ Infra
                    "display_name": aliment_data.nom,
                    "nutrition": {
                        "calories": float(aliment_data.calories or 0.0),
                        "proteines": float(aliment_data.proteines or 0.0),
                        "glucides": float(aliment_data.glucides or 0.0),
                        "lipides": float(aliment_data.lipides or 0.0),
                        "eau": float(aliment_data.eau_ml or 0.0),
                    },
                }
            )
            final_results.append(item)

    return final_results