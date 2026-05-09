from sqlalchemy import func, select
from src.models.aliment import Aliment

# Mapping stratégique pour la démo
# Permet de lier un objet détecté par YOLO à un aliment de ta base Postgres
FOOD_MAPPING = {
    # --- Contenants vers défauts ---
    "bowl": "Oatmeal",           # Mappe vers "Oatmeal (1 cup cooked)"
    "cup": "Coffee",            # Mappe vers "Coffee (black)"
    "wine glass": "Red Wine",   # Mappe vers "Red Wine (5 oz glass)"
    "bottle": "Water",          # Mappe vers "Water"
    # --- Traductions / Précisions ---
    "sandwich": "Turkey Sandwich", 
    "pizza": "Pizza",
    "donut": "Chocolate Donut",
    "cake": "Cupcake",
    "broccoli": "Steamed Broccoli",
    "carrot": "Carrot Sticks",
    "apple": "Apple",
    "banana": "Banana",
    
    # --- Objets à ignorer (Bruit) ---
    "dining table": None,
    "chair": None,
    "refrigerator": None,
    "person": None,
    "fork": None,
    "knife": None,
    "spoon": None
}

async def enrich_with_nutrition(detections, db_session):
    final_results = []
    for item in detections:
        raw_label = item["label"].lower().strip()
        
        # 1. Vérification du mapping
        # On regarde si on doit transformer le label ou ignorer l'objet
        label_to_search = FOOD_MAPPING.get(raw_label, raw_label)
        
        # Si le mapping renvoie None, on passe à l'objet suivant sans l'ajouter
        if label_to_search is None:
            continue

        # 2. Requête SQL avec ILIKE pour plus de souplesse
        query = select(Aliment).where(Aliment.nom.ilike(f"%{label_to_search}%")).order_by(func.length(Aliment.nom))
        result = await db_session.execute(query)
        aliment_data = result.scalars().first()

        if aliment_data:
            item.update(
                {
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
            # On n'ajoute au résultat final que si on a trouvé des infos nutritionnelles
            final_results.append(item)
            
    return final_results