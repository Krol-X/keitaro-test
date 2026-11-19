import os
from typing import Optional
from fastapi import HTTPException, status
import httpx

class KeitaroClient:
    def __init__(self):
        self.base_url = os.getenv("KEITARO_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("KEITARO_API_KEY", "")
        self.timeout = 10.0
        self.headers = {
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, endpoint: str, **kwargs):
        url = f"{self.base_url}/admin_api/v1{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, headers=self.headers, **kwargs)
                if response.status_code == 404:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keitaro resource not found")
                response.raise_for_status()
                if response.status_code == 204 or not response.content:
                    return None
                return response.json()
            except httpx.TimeoutException:
                raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Keitaro timeout")
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Keitaro error: {e.response.text}")

    async def list_campaigns(self, limit: int = 25, offset: int = 0):
        return await self._request("GET", "/campaigns", params={"limit": limit, "offset": offset})

    async def create_campaign(self, data: dict):
        return await self._request("POST", "/campaigns", json=data)

    async def update_campaign(self, campaign_id: int, data: dict):
        return await self._request("PUT", f"/campaigns/{campaign_id}", json=data)

    async def delete_campaign(self, campaign_id: int):
        return await self._request("DELETE", f"/campaigns/{campaign_id}")

    async def get_campaign(self, campaign_id: int):
        return await self._request("GET", f"/campaigns/{campaign_id}")

    async def enable_campaign(self, campaign_id: int):
        return await self._request("POST", f"/campaigns/{campaign_id}/enable")

    async def disable_campaign(self, campaign_id: int):
        return await self._request("POST", f"/campaigns/{campaign_id}/disable")

    async def list_streams(self, campaign_id: int):
        return await self._request("GET", f"/campaigns/{campaign_id}/streams")

    async def create_stream(self, data: dict):
        return await self._request("POST", "/streams", json=data)

    async def get_stream(self, stream_id: int):
        return await self._request("GET", f"/streams/{stream_id}")

    async def update_stream(self, stream_id: int, data: dict):
        return await self._request("PUT", f"/streams/{stream_id}", json=data)

    async def enable_stream(self, stream_id: int):
        return await self._request("POST", f"/streams/{stream_id}/enable")

    async def disable_stream(self, stream_id: int):
        return await self._request("POST", f"/streams/{stream_id}/disable")

    async def list_domains(self):
        return await self._request("GET", "/domains")

    async def list_groups(self):
        return await self._request("GET", "/groups?type=campaigns")

    async def list_traffic_sources(self):
        return await self._request("GET", "/traffic_sources")

    async def list_offers(self):
        return await self._request("GET", "/offers")

    async def list_stream_filters(self):
        return await self._request("GET", "/stream_filters")
