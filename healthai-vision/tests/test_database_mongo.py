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


def test_close_with_client():
    manager = MongoDBManager()
    mock_client = MagicMock()
    manager.client = mock_client
    manager.close()
    mock_client.close.assert_called_once()


def test_close_without_client():
    manager = MongoDBManager()
    manager.close()
