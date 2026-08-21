"""MongoDB repository: per-source collections, idempotent upserts, run log."""

import logging
from collections.abc import Sequence
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import UpdateOne

from debt_monitor.config import Settings
from debt_monitor.models import CollectResult, Observation

logger = logging.getLogger(__name__)

RUNS_COLLECTION = "_runs"
_BULK_CHUNK = 2_000


class MongoRepository:
    """Async data-access layer. One collection per source, plus `_runs`."""

    def __init__(self, settings: Settings) -> None:
        self._client: AsyncIOMotorClient = AsyncIOMotorClient(
            settings.mongo_uri, serverSelectionTimeoutMS=10_000
        )
        self._db: AsyncIOMotorDatabase = self._client[settings.mongo_db_name]
        self._indexed: set[str] = set()

    async def _collection(self, name: str):
        coll = self._db[name]
        if name not in self._indexed:
            # Idempotent in MongoDB; cheap on repeat runs.
            await coll.create_index([("dataset", 1), ("period", 1)])
            self._indexed.add(name)
        return coll

    async def ping(self) -> None:
        await self._db.command("ping")

    async def upsert_observations(
        self, collection: str, observations: Sequence[Observation]
    ) -> int:
        if not observations:
            return 0
        docs = [obs.to_doc() for obs in observations]
        return await self.upsert_docs(collection, docs)

    async def upsert_docs(self, collection: str, docs: Sequence[dict[str, Any]]) -> int:
        """Upsert documents that already carry a deterministic `_id`."""
        if not docs:
            return 0
        coll = await self._collection(collection)
        total = 0
        for i in range(0, len(docs), _BULK_CHUNK):
            chunk = docs[i : i + _BULK_CHUNK]
            ops = [UpdateOne({"_id": doc["_id"]}, {"$set": doc}, upsert=True) for doc in chunk]
            result = await coll.bulk_write(ops, ordered=False)
            total += result.upserted_count + result.modified_count
        return total

    async def record_run(self, result: CollectResult) -> None:
        await self._db[RUNS_COLLECTION].insert_one(result.model_dump(mode="json"))

    async def find_one(self, collection: str, query: dict[str, Any]) -> dict | None:
        return await self._db[collection].find_one(query)

    async def distinct(
        self, collection: str, key: str, query: dict[str, Any] | None = None
    ) -> list[Any]:
        return await self._db[collection].distinct(key, query or {})

    def close(self) -> None:
        self._client.close()
