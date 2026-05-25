from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from src.core.config import settings


class MongoDBManager:
    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.db = None

    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                serverSelectionTimeoutMS=3000,
            )
            await self.client.admin.command("ping")
            self.db = self.client[settings.MONGODB_DB_NAME]
            logger.info("Connecté à MongoDB ({})", settings.MONGODB_DB_NAME)
        except Exception as e:
            logger.warning("MongoDB indisponible — démarrage sans persistance NoSQL : {}", e)
            self.client = None
            self.db = None

    def close(self):
        if self.client:
            self.client.close()
            logger.info("Connexion MongoDB fermée")


mongo_db = MongoDBManager()
