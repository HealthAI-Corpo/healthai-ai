import json
from typing import Any

import httpx

from src.core.config import settings


async def generate_llm_prediction(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Interroge Ollama en JSON strict avec un timeout étendu pour les inférences CPU."""
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": f"System: {system_prompt}\nUser: {user_prompt}",
        "format": "json",
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

        raw_text = response.json().get("response", "").strip()

        # Nettoyage des balises markdown si le LLM en génère
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
            raise ValueError(f"Le LLM n'a pas renvoyé un JSON valide : {raw_text}") from e
