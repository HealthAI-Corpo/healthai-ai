import os

from motor.motor_asyncio import AsyncIOMotorClient


class MongoDBManager:
    def __init__(self):
        self.client = None
        self.db = None

    def connect(self):
        # On récupère l'URL de l'env (configurée dans le docker-compose)
        mongo_url = os.getenv("MONGODB_URL", "mongodb://mongo:27017")
        self.client = AsyncIOMotorClient(mongo_url)
        # On définit le nom de la base de données
        self.db = self.client.healthai_db
        print("Connecté à MongoDB")

    def close(self):
        if self.client:
            self.client.close()


# On instancie le manager
mongo_db = MongoDBManager()
