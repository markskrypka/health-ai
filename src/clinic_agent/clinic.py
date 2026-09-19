"""Client for the Prosper platform API: the read-only clinic and the submission routes.

The clinic is static for the whole event, so the catalogue is fetched once per
process and held. HTTP is stateless and safe to share across calls; everything
a call owns lives in its CallSession, never here.
"""

import json
from typing import Any

import httpx

from . import config


class ClinicError(Exception):
    def __init__(self, status: int, detail: Any):
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


class ClinicClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        root_url = (base_url or config.PROSPER_BASE_URL).rstrip("/")
        api_url = root_url if root_url.endswith("/api/v1") else f"{root_url}/api/v1"
        self._http = httpx.AsyncClient(
            base_url=api_url,
            headers={"X-Api-Key": api_key or config.PROSPER_API_KEY},
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        self._catalogue: dict | None = None

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict | list | None = None) -> dict:
        resp = await self._http.get(path, params=params)
        if resp.status_code != 200:
            raise ClinicError(resp.status_code, _detail(resp))
        return resp.json()

    async def catalogue(self) -> dict:
        """Providers, specialties, types, sites, plans, restrictions, calendar."""
        if self._catalogue is None:
            try:
                self._catalogue = await self._get("/clinic")
            except (httpx.HTTPError, ClinicError):
                # The catalogue never changes during the event; the snapshot is the same data.
                self._catalogue = json.loads((config.ORGANIZERS_DIR / "clinic.json").read_text())
        return self._catalogue

    async def directory(self, **fields: str) -> list[dict]:
        """Search patients. An exact field that does not match excludes the patient."""
        params = {k: v for k, v in fields.items() if v}
        return (await self._get("/directory", params))["matches"]

    async def availability(
        self,
        date_from: str,
        date_to: str,
        *,
        provider_id: str | None = None,
        specialty_id: str | None = None,
        location_id: str | None = None,
        patient_id: str | None = None,
        insurers: list[str] | None = None,
    ) -> dict:
        """Window of at most 14 days. With patient_id the API applies age, history and plans."""
        params: list[tuple[str, str]] = [("date_from", date_from), ("date_to", date_to)]
        for key, value in (
            ("provider_id", provider_id),
            ("specialty_id", specialty_id),
            ("location_id", location_id),
            ("patient_id", patient_id),
        ):
            if value:
                params.append((key, value))
        for insurer in insurers or []:
            params.append(("insurer", insurer))
        return await self._get("/availability", params)

    async def appointments(self, patient_id: str, when: str = "upcoming") -> list[dict]:
        return (await self._get(f"/patients/{patient_id}/appointments", {"when": when}))["appointments"]

    async def submit(self, action: str, payload: dict) -> tuple[int, Any]:
        """POST /submit/<action>. Returns (status, body); 409 means an identical retry."""
        # Short per attempt, so that several attempts fit inside the 30 s submission window.
        resp = await self._http.post(f"/submit/{action}", json=payload, timeout=httpx.Timeout(7.0, connect=4.0))
        return resp.status_code, _detail(resp)


def _detail(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text
