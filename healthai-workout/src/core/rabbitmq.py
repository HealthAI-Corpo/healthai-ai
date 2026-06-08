"""RabbitMQ — bus de messages entre le front et les services IA.

Rôle dans l'architecture :
    Front → RabbitMQ → Worker(workout) → MongoDB (job résultat)

Pattern :
    - Les routes LLM publient un message dans la queue `healthai.ai.jobs.workout`
      au lieu de lancer une FastAPI BackgroundTask.
    - Le worker (démarré dans le lifespan) consomme la queue avec prefetch_count=1
      pour ne pas saturer Ollama sous charge.
    - L'API de polling (GET /ai/jobs/{job_id}) reste inchangée — le résultat est
      toujours stocké dans MongoDB par `job_service.run_in_background`.

Fallback :
    Si RABBITMQ_URL est vide (dev sans broker), `is_available()` renvoie False et
    les routes retombent sur BackgroundTasks.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from loguru import logger

from src.core.config import settings

QUEUE_NAME = "healthai.ai.jobs.workout"

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None


def is_available() -> bool:
    return bool(settings.RABBITMQ_URL)


async def connect() -> None:
    global _connection, _channel
    if not is_available():
        logger.info("RABBITMQ_URL non configuré — mode BackgroundTasks actif")
        return
    try:
        _connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL,
            reconnect_interval=5,
        )
        _channel = await _connection.channel()
        await _channel.set_qos(prefetch_count=1)
        await _channel.declare_queue(QUEUE_NAME, durable=True)
        logger.info("RabbitMQ connecté — queue '{}'", QUEUE_NAME)
    except Exception as e:
        logger.warning("RabbitMQ indisponible — fallback BackgroundTasks : {}", e)
        _connection = None
        _channel = None


async def close() -> None:
    global _connection, _channel
    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("RabbitMQ déconnecté")
    _connection = None
    _channel = None


async def publish(message: dict[str, Any]) -> None:
    """Publie un message JSON dans la queue des jobs IA workout."""
    if _channel is None:
        raise RuntimeError("RabbitMQ non connecté")
    await _channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(message).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=QUEUE_NAME,
    )


async def start_worker(
    dispatch: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Lance le consumer en tâche de fond (bloquant tant que la connexion tient)."""
    if _channel is None:
        return
    queue = await _channel.get_queue(QUEUE_NAME)

    async def _on_message(msg: AbstractIncomingMessage) -> None:
        async with msg.process(requeue=True):
            try:
                payload = json.loads(msg.body)
                await dispatch(payload)
            except Exception as e:  # noqa: BLE001
                logger.exception("Erreur traitement message RabbitMQ : {}", e)

    await queue.consume(_on_message)
    logger.info("Worker RabbitMQ actif sur '{}'", QUEUE_NAME)
    # Reste en vie tant que la connexion est ouverte
    await asyncio.Future()
