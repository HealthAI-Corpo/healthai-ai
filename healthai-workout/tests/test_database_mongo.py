from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database_mongo import MongoDBManager


@pytest.mark.asyncio
async def test_connect_success():
    manager = MongoDBManager()
    mock_client = MagicMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})
    mock_client.__getitem__ = MagicMock(return_value=MagicMock())

    with patch("src.database_mongo.AsyncIOMotorClient", return_value=mock_client):
        await manager.connect()

    assert manager.client is not None
    assert manager.db is not None


@pytest.mark.asyncio
async def test_connect_failure_fallback():
    manager = MongoDBManager()
    mock_client = MagicMock()
    mock_client.admin.command = AsyncMock(side_effect=Exception("Server selection timeout"))

    with patch("src.database_mongo.AsyncIOMotorClient", return_value=mock_client):
        await manager.connect()

    assert manager.client is None
    assert manager.db is None


@pytest.mark.asyncio
async def test_insert_document():
    manager = MongoDBManager()
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="abc123"))
    manager.db = MagicMock()
    manager.db.recommendations = mock_collection

    result = await manager.db.recommendations.insert_one(
        {"utilisateur_id": "1", "exercices": ["squat", "bench"]}
    )

    assert result.inserted_id == "abc123"
    mock_collection.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_by_utilisateur_id():
    manager = MongoDBManager()
    expected = {"utilisateur_id": "42", "exercices": ["deadlift"]}
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=expected)
    manager.db = MagicMock()
    manager.db.recommendations = mock_collection

    result = await manager.db.recommendations.find_one({"utilisateur_id": "42"})

    assert result == expected
    assert result["utilisateur_id"] == "42"


def test_close_with_client():
    manager = MongoDBManager()
    mock_client = MagicMock()
    manager.client = mock_client
    manager.close()
    mock_client.close.assert_called_once()


def test_close_without_client():
    manager = MongoDBManager()
    manager.close()
