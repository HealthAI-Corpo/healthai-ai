import json

import httpx


class LLMJsonError(ValueError):
    """Le LLM a renvoyé un texte que l'on n'a pas réussi à parser en JSON.

    Le texte brut est exposé via `raw_text` pour permettre de le tracer dans les
    jobs (debug : prompts vs sortie réellement reçue d'Ollama).
    """

    def __init__(self, raw_text: str, original: Exception | None = None) -> None:
        super().__init__(f"Le LLM n'a pas renvoyé un JSON valide. Texte brut reçu : {raw_text}")
        self.raw_text = raw_text
        self.original = original


async def generate_llm_prediction_with_raw(
    base_url: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    response_format: str | dict = "json",
    options: dict | None = None,
) -> tuple[str, dict]:
    """Version "verbose" du client Ollama : renvoie aussi le texte brut.

    Utile pour les jobs IA qui veulent tracer le `raw_response` (succès ET échec)
    et pour le debug des sorties LLM mal formées. En cas de JSON invalide, lève
    `LLMJsonError(raw_text)`.
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
        return raw_text, json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LLMJsonError(raw_text, original=exc) from exc


async def generate_llm_prediction(
    base_url: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    response_format: str | dict = "json",
    options: dict | None = None,
) -> dict:
    """Client Ollama générique : envoie les prompts et force un retour JSON.

    Variante historique qui ne renvoie que le JSON parsé ; conservée pour les
    appelants qui n'ont pas besoin du texte brut (vision, etc.). Pour tracer le
    `raw_response` dans un job, utiliser `generate_llm_prediction_with_raw`.
    """
    _, parsed = await generate_llm_prediction_with_raw(
        base_url=base_url,
        model_name=model_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_format=response_format,
        options=options,
    )
    return parsed


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
        "required": [
            "titre_repas",
            "estimation_calories",
            "ingredients",
            "instructions",
        ],
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
