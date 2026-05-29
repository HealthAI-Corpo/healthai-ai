"""Détection d'aliments par YOLO + enrichissement nutritionnel + persistance."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile

from src.database import AsyncSessionLocal
from src.database_mongo import mongo_db
from src.schemas.vision import AnalyzeResponse
from src.services.ai_service import ai_service
from src.services.nutrition_service import enrich_with_nutrition

router = APIRouter(tags=["Vision Analysis"])


async def _get_db_sql():
    async with AsyncSessionLocal() as session:
        yield session


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyse photo d'un repas",
    description=(
        "Détecte les aliments présents sur une image (YOLOv8, seuil 0.5), recherche les "
        "macros dans la table Postgres `aliment`, persiste un document `consumptions` dans "
        "Mongo et renvoie le résumé. Le `consumption_id` retourné sert ensuite à demander "
        "des conseils via `POST /nutrition/ai/advice`."
    ),
)
async def analyze_meal(
    file: UploadFile = File(..., description="Image JPEG/PNG du repas"),
    x_user_id: str = Header(..., alias="X-User-Id"),
    db_sql=Depends(_get_db_sql),
) -> AnalyzeResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Format de fichier non supporté.")

    try:
        image_bytes = await file.read()
        raw_results = ai_service.analyze_image(image_bytes)
        enriched_results = await enrich_with_nutrition(raw_results, db_sql)

        total_repas = {
            "calories": sum(
                item.get("nutrition", {}).get("calories", 0) for item in enriched_results
            ),
            "proteines": sum(
                item.get("nutrition", {}).get("proteines", 0) for item in enriched_results
            ),
            "glucides": sum(
                item.get("nutrition", {}).get("glucides", 0) for item in enriched_results
            ),
            "lipides": sum(
                item.get("nutrition", {}).get("lipides", 0) for item in enriched_results
            ),
            "eau_ml": sum(
                item.get("nutrition", {}).get("eau", 0) for item in enriched_results
            ),
        }

        consumption_doc = {
            "user_id": x_user_id,  # gardé en string : c'est ainsi qu'il est requêté plus loin
            "timestamp": datetime.utcnow(),
            "summary": total_repas,
            "details": enriched_results,
        }

        inserted_id = None
        if mongo_db.db is not None:
            result_mongo = await mongo_db.db.consumptions.insert_one(consumption_doc)
            inserted_id = str(result_mongo.inserted_id)

        return AnalyzeResponse(
            filename=file.filename,
            user_id=x_user_id,
            consumption_id=inserted_id,
            count=len(enriched_results),
            total_repas=total_repas,
            detections=enriched_results,
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse : {e}") from e
