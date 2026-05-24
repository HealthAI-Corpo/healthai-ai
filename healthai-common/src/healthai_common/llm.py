import json
import httpx


async def generate_llm_prediction(
    base_url: str, model_name: str, system_prompt: str, user_prompt: str
) -> dict:
    """Envoie les prompts à Ollama, gère les temps de charge CPU et force un retour au format JSON strict."""
    url = f"{base_url}/api/generate"

    payload = {
        "model": model_name,
        "prompt": f"System: {system_prompt}\nUser: {user_prompt}",
        "format": "json",
        "stream": False,
    }

    #  Augmenté à 180s (3 minutes) pour laisser le temps au CPU de charger le runner sans couper
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
            # Si le parsing échoue, on lève une erreur claire pour les logs de vision
            raise ValueError(
                f"Le LLM n'a pas renvoyé un JSON valide. Texte brut reçu : {raw_text}"
            ) from e
