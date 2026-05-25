import json

import httpx


async def generate_llm_prediction(
    base_url: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    response_format: str | dict = "json",
    options: dict | None = None,
) -> dict:
    """Client Ollama générique : envoie les prompts et force un retour JSON.

    response_format : "json" (souple, défaut) ou un schéma JSON strict (dict) pour
    contraindre la structure de sortie. options : paramètres Ollama (temperature,
    num_predict, num_threads...). Gère les temps de charge CPU (timeout 180 s).
    """
    url = f"{base_url}/api/generate"

    payload = {
        "model": model_name,
        "prompt": f"System: {system_prompt}\nUser: {user_prompt}",
        "format": response_format,
        "stream": False,
    }
    if options:
        payload["options"] = options

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()

        raw_text = result.get("response", "").strip()

        #  Nettoyage des balises Markdown (```json ... ```) si le LLM en a ajouté
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            # Si le parsing échoue, on lève une erreur claire pour les logs appelants
            raise ValueError(
                f"Le LLM n'a pas renvoyé un JSON valide. Texte brut reçu : {raw_text}"
            ) from e


async def generate_meal_suggestion(
    base_url: str, model_name: str, system_prompt: str, user_prompt: str
) -> dict:
    """Force Qwen à générer une suggestion de repas avec un schéma JSON strict."""
    url = f"{base_url}/api/generate"

    recipe_schema = {
        "type": "object",
        "properties": {
            "titre_repas": {"type": "string"},
            "estimation_calories": {"type": "string"},
            "ingredients": {"type": "string"},
            "instructions": {"type": "string"},
        },
        "required": ["titre_repas", "estimation_calories", "ingredients", "instructions"],
    }

    payload = {
        "model": model_name,
        "prompt": f"System: {system_prompt}\nUser: {user_prompt}",
        "format": recipe_schema,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 180,
            "num_thread": 4,
        },
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        raw_text = result.get("response", "").strip()
        return json.loads(raw_text)
