from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Iterable

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured")

SQL: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


class ModelABC(ABC):
    def __init__(self, table: str):
        self._table = table

    @abstractmethod
    async def select(self, columns: str = "*", where: dict[str, Any] | None = None,
                     limit: int = -1, order_by: str | None = None,
                     ascending: bool = True) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def insert(self, values: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def update(self, values: dict[str, Any], where: dict[str, Any]) -> int: ...

    @abstractmethod
    async def delete(self, where: dict[str, Any]) -> int: ...


class TableModel(ModelABC):
    def _query(self, columns: str = "*", where: dict[str, Any] | None = None):
        query = SQL.table(self._table).select(columns)
        for column, value in (where or {}).items():
            query = query.eq(column, value)
        return query

    async def select(self, columns: str = "*", where: dict[str, Any] | None = None,
                     limit: int = -1, order_by: str | None = None,
                     ascending: bool = True) -> list[dict[str, Any]]:
        query = self._query(columns, where)
        if order_by:
            query = query.order(order_by, desc=not ascending)
        if limit >= 0:
            query = query.limit(limit)
        return list(query.execute().data or [])

    async def insert(self, values: dict[str, Any]) -> dict[str, Any]:
        result = SQL.table(self._table).insert(values).execute()
        if not result.data:
            raise RuntimeError(f"Supabase insert returned no row for {self._table}")
        return dict(result.data[0])

    async def update(self, values: dict[str, Any], where: dict[str, Any]) -> int:
        result = SQL.table(self._table).update(values)
        for column, value in where.items():
            result = result.eq(column, value)
        result = result.select("*")
        response = result.execute()
        return len(response.data or [])

    async def delete(self, where: dict[str, Any]) -> int:
        result = SQL.table(self._table).delete()
        for column, value in where.items():
            result = result.eq(column, value)
        result = result.select("*")
        response = result.execute()
        return len(response.data or [])


def DefineTable() -> None:
    return None


initialize_database = DefineTable
