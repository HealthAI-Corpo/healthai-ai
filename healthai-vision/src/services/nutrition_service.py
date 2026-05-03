from sqlalchemy import select, func
from src.models.aliment import Aliment 

async def enrich_with_nutrition(detections, db_session):
    final_results = []
    for item in detections:
        label_to_search = item['label'].lower().strip()
        
        query = select(Aliment).where(func.lower(func.trim(Aliment.nom)) == label_to_search)
        result = await db_session.execute(query)
        aliment_data = result.scalar_one_or_none()

        if aliment_data:
            item.update({
                "display_name": aliment_data.nom,
                "nutrition": {
                    # On convertit explicitement en float pour éviter l'erreur JSON
                    "calories": float(aliment_data.calories) if aliment_data.calories is not None else 0.0,
                    "proteines": float(aliment_data.proteines) if aliment_data.proteines is not None else 0.0,
                    "glucides": float(aliment_data.glucides) if aliment_data.glucides is not None else 0.0,
                    "lipides": float(aliment_data.lipides) if aliment_data.lipides is not None else 0.0
                }
            })
        final_results.append(item)
    return final_results