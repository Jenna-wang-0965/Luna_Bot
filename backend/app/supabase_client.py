from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter


@dataclass(frozen=True)
class SupabaseRest:
    base_rest_url: str  # e.g. https://xxx.supabase.co/rest/v1
    service_role_key: str

    def _headers(self) -> dict[str, str]:
        # For PostgREST: apikey + Authorization.
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=0.2, max=2.0))
    def _request(
        self,
        method: Literal["GET", "POST", "PATCH"],
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Any | None = None,
        prefer: str | None = None,
    ) -> httpx.Response:
        headers = self._headers()
        if prefer:
            headers["Prefer"] = prefer
        with httpx.Client(timeout=20.0) as client:
            resp = client.request(method, f"{self.base_rest_url}{path}", headers=headers, params=params, json=json)
        resp.raise_for_status()
        return resp

    def select(self, table_or_view: str, *, select: str = "*", params: Optional[dict[str, Any]] = None) -> list[dict]:
        p = {"select": select}
        if params:
            p.update(params)
        resp = self._request("GET", f"/{table_or_view}", params=p)
        return resp.json()

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        resp = self._request("POST", f"/{table}", json=row, prefer="return=representation")
        data = resp.json()
        return data[0] if isinstance(data, list) and data else data

    def patch(self, table: str, *, match: dict[str, Any], patch: dict[str, Any]) -> int:
        # PostgREST filter syntax: col=eq.value
        params = {k: f"eq.{v}" for k, v in match.items()}
        resp = self._request("PATCH", f"/{table}", params=params, json=patch, prefer="return=minimal")
        return int(resp.headers.get("Content-Range", "0").split("/")[-1] or 0)

