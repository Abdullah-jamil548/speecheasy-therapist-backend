from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings


class SupabaseRest:
    """Minimal Supabase REST client using the service role key."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self.base = settings.supabase_url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base, headers=self.headers, timeout=30.0)

    def select(
        self,
        table: str,
        *,
        filters: dict[str, str] | None = None,
        columns: str = "*",
        order: str | None = None,
        limit: int | None = None,
        single: bool = False,
    ) -> Any:
        params: dict[str, str] = {"select": columns}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        headers = dict(self.headers)
        if single:
            headers["Accept"] = "application/vnd.pgrst.object+json"
        with self._client() as client:
            res = client.get(f"/{table}", params=params, headers=headers)
            res.raise_for_status()
            if res.status_code == 204 or not res.content:
                return None if single else []
            return res.json()

    def insert(self, table: str, row: dict[str, Any] | list[dict[str, Any]]) -> Any:
        with self._client() as client:
            res = client.post(f"/{table}", json=row)
            if res.is_error:
                raise RuntimeError(res.text)
            return res.json()

    def update(self, table: str, filters: dict[str, str], patch: dict[str, Any]) -> Any:
        with self._client() as client:
            res = client.patch(f"/{table}", params=filters, json=patch)
            if res.is_error:
                raise RuntimeError(res.text)
            return res.json()

    def delete(self, table: str, filters: dict[str, str]) -> None:
        with self._client() as client:
            res = client.delete(f"/{table}", params=filters)
            if res.is_error:
                raise RuntimeError(res.text)


_db: SupabaseRest | None = None


def get_db() -> SupabaseRest:
    global _db
    if _db is None:
        _db = SupabaseRest()
    return _db
