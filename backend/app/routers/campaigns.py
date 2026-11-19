import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator

from app.database import get_db, init_db
from app.models import Operation
from app.keitaro_client import KeitaroClient

router = APIRouter(prefix="/api/v1", tags=["campaigns"])
keitaro = KeitaroClient()

# --- Модели запросов/ответов ---

class CampaignItem(BaseModel):
    campaign_id: int
    name: str
    group_name: Optional[str] = None
    traffic_source_name: Optional[str] = None
    state: str

class CampaignListResponse(BaseModel):
    items: List[CampaignItem]
    limit: int
    offset: int
    has_more: bool

class ReferenceResponse(BaseModel):
    domains: List[Dict[str, Any]]
    groups: List[Dict[str, Any]]
    traffic_sources: List[Dict[str, Any]]
    countries: List[Dict[str, Any]]
    defaults: Dict[str, Optional[int]]

class OfferItem(BaseModel):
    offer_id: int
    name: str

class CreateCampaignRequest(BaseModel):
    name: str
    excluded_countries: List[str]
    offer_id: int
    domain_id: Optional[int] = None
    group_id: Optional[int] = None
    traffic_source_id: Optional[int] = None

    @validator("name")
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @validator("excluded_countries")
    def countries_valid(cls, v):
        if not v:
            raise ValueError("Excluded countries list cannot be empty")
        normalized = sorted(set(c.upper() for c in v))
        return normalized

class StreamOfferUpdate(BaseModel):
    offer_id: int
    share: int = Field(ge=0, le=100)
    state: str = "active"

    @validator("state")
    def valid_state(cls, value):
        if value not in {"active", "disabled"}:
            raise ValueError("Offer state must be active or disabled")
        return value

class StreamOffersRequest(BaseModel):
    offers: List[StreamOfferUpdate]

# --- Помощники ---

def hash_request(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def response_items(response: Any) -> List[Dict[str, Any]]:
    """Accept both Keitaro list responses and paginated {items: [...]} responses."""
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        items = response.get("items", [])
        if isinstance(items, list):
            return items
    raise HTTPException(status_code=502, detail="Unexpected list response from Keitaro API")


def related_name(value: Any) -> Optional[str]:
    """Extract a name from related objects returned as either objects or arrays."""
    if isinstance(value, dict):
        return value.get("name")
    if isinstance(value, list):
        return next((item.get("name") for item in value if isinstance(item, dict) and item.get("name")), None)
    return value if isinstance(value, str) else None


def generated_campaign_alias(name: str, idempotency_key: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "campaign"
    suffix = hashlib.sha256(idempotency_key.encode()).hexdigest()[:8]
    return f"{slug[:40]}-{suffix}"


def configured_id(requested: Optional[int], env_name: str) -> Optional[int]:
    if requested is not None:
        return requested
    value = os.getenv(env_name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"{env_name} must contain an integer ID") from exc


def normalize_streams(response: Any) -> List[Dict[str, Any]]:
    streams = []
    for stream in response_items(response):
        item = dict(stream)
        item.setdefault("stream_id", item.get("id"))
        item.setdefault("offers", [])
        streams.append(item)
    return streams

# --- Маршруты ---

@router.get("/campaigns")
async def list_campaigns(
    query: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    try:
        keitaro_res = await keitaro.list_campaigns(limit=1000, offset=0)
        groups = {g["id"]: g["name"] for g in response_items(await keitaro.list_groups())}
        sources = {s["id"]: s["name"] for s in response_items(await keitaro.list_traffic_sources())}
        items = []
        for c in response_items(keitaro_res):
            items.append(CampaignItem(
                campaign_id=c["id"],
                name=c["name"],
                group_name=related_name(c.get("group")) or groups.get(c.get("group_id")),
                traffic_source_name=related_name(c.get("traffic_source")) or sources.get(c.get("traffic_source_id")),
                state=c["state"]
            ))

        items.sort(key=lambda x: x.campaign_id, reverse=True)

        if query:
            if query.isdigit():
                items = [i for i in items if i.campaign_id == int(query)]
            else:
                items = [i for i in items if query.lower() in i.name.lower()]

        paginated = items[offset : offset + limit]
        has_more = (offset + limit) < len(items)

        return CampaignListResponse(
            items=paginated,
            limit=limit,
            offset=offset,
            has_more=has_more
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.get("/references")
async def get_references():
    domains = await keitaro.list_domains()
    groups = await keitaro.list_groups()
    traffic_sources = await keitaro.list_traffic_sources()

    countries = [
        {"code": "PL", "name": "Poland"},
        {"code": "LT", "name": "Lithuania"},
        {"code": "RU", "name": "Russia"},
        {"code": "NL", "name": "Netherlands"}
    ]

    return ReferenceResponse(
        domains=[{"id": d["id"], "name": d["name"]} for d in response_items(domains)],
        groups=[{"id": g["id"], "name": g["name"]} for g in response_items(groups)],
        traffic_sources=[{"id": t["id"], "name": t["name"]} for t in response_items(traffic_sources)],
        countries=countries,
        defaults={
            "domain_id": configured_id(None, "DEFAULT_DOMAIN_ID"),
            "group_id": configured_id(None, "DEFAULT_GROUP_ID"),
            "traffic_source_id": configured_id(None, "DEFAULT_TRAFFIC_SOURCE_ID")
        }
    )

@router.get("/offers")
async def list_offers(query: Optional[str] = Query(None)):
    res = await keitaro.list_offers()
    offers = response_items(res)
    if query:
        normalized_query = query.casefold()
        offers = [
            offer for offer in offers
            if normalized_query in str(offer.get("name", "")).casefold()
            or normalized_query == str(offer.get("id", ""))
        ]
    items = [OfferItem(offer_id=o["id"], name=o["name"]) for o in offers[:25]]
    return {"items": items}

@router.post("/campaigns", status_code=201)
async def create_campaign(
    request: CreateCampaignRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    req_hash = hash_request(request.dict())

    existing_op = db.query(Operation).filter(Operation.idempotency_key == idempotency_key).first()
    if existing_op:
        if existing_op.request_hash == req_hash:
            if existing_op.status == "succeeded":
                campaign = await keitaro.get_campaign(existing_op.campaign_id)
                streams = await keitaro.list_streams(existing_op.campaign_id)
                return {
                    "campaign_id": campaign["id"],
                    "name": campaign["name"],
                    "state": campaign["state"],
                    "campaign_url": campaign.get("url"),
                    "domain_id": campaign.get("domain_id"),
                    "domain_name": related_name(campaign.get("domain")),
                    "group_id": campaign.get("group_id"),
                    "group_name": related_name(campaign.get("group")),
                    "traffic_source_id": campaign.get("traffic_source_id"),
                    "traffic_source_name": related_name(campaign.get("traffic_source")),
                    "streams": normalize_streams(streams)
                }
            return {"operation_id": existing_op.id, "stage": existing_op.stage, "status": existing_op.status}
        else:
            raise HTTPException(status_code=409, detail="Idempotency key conflict with different request")

    op = Operation(
        type="create_campaign",
        status="running",
        stage="validation",
        idempotency_key=idempotency_key,
        request_hash=req_hash,
        user_id="system"
    )
    db.add(op)
    db.commit()

    try:
        offers = await keitaro.list_offers()
        if not any(o["id"] == request.offer_id for o in response_items(offers)):
            raise HTTPException(status_code=422, detail="Offer not found", field="offer_id")

        alias = generated_campaign_alias(request.name, idempotency_key)
        keitaro_data = {
            "alias": alias,
            "name": request.name,
            "state": "disabled",
        }
        for field, env_name in (
            ("domain_id", "DEFAULT_DOMAIN_ID"),
            ("group_id", "DEFAULT_GROUP_ID"),
            ("traffic_source_id", "DEFAULT_TRAFFIC_SOURCE_ID"),
        ):
            value = configured_id(getattr(request, field), env_name)
            if value is not None:
                keitaro_data[field] = str(value) if field == "group_id" else value

        campaign = await keitaro.create_campaign(keitaro_data)
        campaign_id = campaign["id"]
        alias = campaign.get("alias", f"cmp_{campaign_id}")

        op.campaign_id = campaign_id
        op.alias = alias
        op.stage = "streams_creation"
        db.commit()

        stream_filters = response_items(await keitaro.list_stream_filters())
        country_filter = next(
            (item for item in stream_filters if str(item.get("value", "")).casefold() in {"country", "countries"}),
            None,
        )
        if country_filter is None:
            raise HTTPException(status_code=502, detail="Keitaro does not expose a country stream filter")

        await keitaro.create_stream({
            "campaign_id": campaign_id,
            "name": "Forced Redirect (Google)",
            "position": 1,
            "type": "forced",
            "schema": "redirect",
            "action_type": "http",
            "action_payload": "https://www.google.com/",
            "collect_clicks": True,
            "filters": [{
                "name": country_filter["value"],
                "mode": "accept",
                "payload": request.excluded_countries,
            }],
        })

        await keitaro.create_stream({
            "campaign_id": campaign_id,
            "name": "Default Stream",
            "position": 2,
            "type": "default",
            "schema": "landings",
            "action_type": "http",
            "collect_clicks": True,
            "offers": [{"offer_id": request.offer_id, "share": 100, "state": "active"}],
        })

        await keitaro.enable_campaign(campaign_id)

        op.status = "succeeded"
        op.stage = "completed"
        db.commit()

        final_campaign = await keitaro.get_campaign(campaign_id)
        streams = await keitaro.list_streams(campaign_id)

        return {
            "campaign_id": campaign_id,
            "name": final_campaign["name"],
            "state": final_campaign["state"],
            "campaign_url": final_campaign.get("url"),
            "domain_id": final_campaign.get("domain_id"),
            "domain_name": related_name(final_campaign.get("domain")),
            "group_id": final_campaign.get("group_id"),
            "group_name": related_name(final_campaign.get("group")),
            "traffic_source_id": final_campaign.get("traffic_source_id"),
            "traffic_source_name": related_name(final_campaign.get("traffic_source")),
            "streams": normalize_streams(streams)
        }

    except HTTPException:
        op.status = "failed"
        op.error_code = "UPSTREAM_OR_VALIDATION_ERROR"
        db.commit()
        raise
    except Exception as e:
        op.status = "failed"
        op.error_code = "INTERNAL_ERROR"
        db.commit()
        raise HTTPException(status_code=502, detail=str(e))

@router.get("/campaigns/{campaign_id}")
async def get_campaign_detail(campaign_id: int):
    campaign = await keitaro.get_campaign(campaign_id)
    streams = await keitaro.list_streams(campaign_id)

    return {
        "campaign_id": campaign["id"],
        "name": campaign["name"],
        "state": campaign["state"],
        "campaign_url": campaign.get("url"),
        "domain_id": campaign.get("domain_id"),
        "domain_name": related_name(campaign.get("domain")),
        "group_id": campaign.get("group_id"),
        "group_name": related_name(campaign.get("group")),
        "traffic_source_id": campaign.get("traffic_source_id"),
        "traffic_source_name": related_name(campaign.get("traffic_source")),
        "streams": normalize_streams(streams)
    }

@router.put("/campaigns/{campaign_id}/streams/{stream_id}/offers")
async def update_stream_offers(
    campaign_id: int,
    stream_id: int,
    request: StreamOffersRequest,
    db: Session = Depends(get_db)
):
    op = Operation(type="update_offers", status="running", stage="validation")
    db.add(op)
    db.commit()

    try:
        stream = await keitaro.get_stream(stream_id)
        if stream.get("campaign_id") != campaign_id:
            raise HTTPException(status_code=404, detail="Stream does not belong to campaign")

        keitaro_update = {
            "offers": [offer.dict() for offer in request.offers]
        }
        updated_stream = await keitaro.update_stream(stream_id, keitaro_update)

        op.status = "succeeded"
        db.commit()
        return {"offers": updated_stream.get("offers", [])}

    except HTTPException:
        op.status = "failed"
        db.commit()
        raise
    except Exception as e:
        op.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=str(e))

@router.get("/operations/{operation_id}")
async def get_operation_status(operation_id: str, db: Session = Depends(get_db)):
    op = db.query(Operation).filter(Operation.id == operation_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")
    return {
        "operation_id": op.id,
        "status": op.status,
        "stage": op.stage,
        "campaign_id": op.campaign_id,
        "stream_id": op.stream_id,
        "error_code": op.error_code
    }
