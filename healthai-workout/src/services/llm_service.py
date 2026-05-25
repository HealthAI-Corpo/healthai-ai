from typing import Any

from healthai_common.llm import generate_llm_prediction as _generate_llm_prediction

from src.core.config import settings


async def generate_llm_prediction(
    system_prompt: str,
    user_prompt: str,
    response_format: str | dict = "json",
    options: dict | None = None,
) -> dict[str, Any]:
    """Appelle Ollama via la bibliothèque partagée healthai-common, avec la config du service.

    response_format : "json" (souple) ou un schéma JSON strict (dict) pour contraindre la
    structure de sortie d'Ollama. options : paramètres Ollama (temperature, num_predict...).
    """
    return await _generate_llm_prediction(
        base_url=settings.OLLAMA_BASE_URL,
        model_name=settings.OLLAMA_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_format=response_format,
        options=options,
    )
