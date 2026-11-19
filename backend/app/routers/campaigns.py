import hashlib
import json
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
        normalized = list(set(c.upper() for c in v))
        return normalized

class StreamOfferUpdate(BaseModel):
    offer_id: int

class StreamOffersRequest(BaseModel):
    revision: str
    distribution: str
    offers: List[StreamOfferUpdate]

    @validator("distribution")
    def valid_distribution(cls, v):
        if v not in ["equal", "explicit"]:
            raise ValueError("Distribution must be 'equal' or 'explicit'")
        return v

# --- Помощники ---

def hash_request(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

# --- Маршруты ---

@router.get("/campaigns")
async def list_campaigns(
    query: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    try:
        keitaro_res = await keitaro.list_campaigns(query=query, limit=1000, offset=0)
        items = []
        for c in keitaro_res.get("items", []):
            items.append(CampaignItem(
                campaign_id=c["id"],
                name=c["name"],
                group_name=c.get("group", {}).get("name") if c.get("group") else None,
                traffic_source_name=c.get("traffic_source", {}).get("name") if c.get("traffic_source") else None,
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
        domains=[{"id": d["id"], "name": d["name"]} for d in domains.get("items", [])],
        groups=[{"id": g["id"], "name": g["name"]} for g in groups.get("items", [])],
        traffic_sources=[{"id": t["id"], "name": t["name"]} for t in traffic_sources.get("items", [])],
        countries=countries,
        defaults={
            "domain_id": int(os.getenv("DEFAULT_DOMAIN_ID", 0)) or None,
            "group_id": int(os.getenv("DEFAULT_GROUP_ID", 0)) or None,
            "traffic_source_id": int(os.getenv("DEFAULT_TRAFFIC_SOURCE_ID", 0)) or None
        }
    )

@router.get("/offers")
async def list_offers(query: Optional[str] = Query(None)):
    res = await keitaro.list_offers(query=query)
    items = [OfferItem(offer_id=o["id"], name=o["name"]) for o in res.get("items", [])[:25]]
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
                    "domain_name": campaign.get("domain", {}).get("name"),
                    "group_id": campaign.get("group_id"),
                    "group_name": campaign.get("group", {}).get("name"),
                    "traffic_source_id": campaign.get("traffic_source_id"),
                    "traffic_source_name": campaign.get("traffic_source", {}).get("name"),
                    "streams": streams.get("items", [])
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
        offers = await keitaro.list_offers(query=str(request.offer_id))
        if not any(o["id"] == request.offer_id for o in offers.get("items", [])):
            raise HTTPException(status_code=422, detail="Offer not found", field="offer_id")
        
        keitaro_data = {
            "name": request.name,
            "domain_id": request.domain_id or os.getenv("DEFAULT_DOMAIN_ID"),
            "group_id": request.group_id or os.getenv("DEFAULT_GROUP_ID"),
            "traffic_source_id": request.traffic_source_id or os.getenv("DEFAULT_TRAFFIC_SOURCE_ID"),
            "state": "disabled"
        }
        campaign = await keitaro.create_campaign(keitaro_data)
        campaign_id = campaign["id"]
        alias = campaign.get("alias", f"cmp_{campaign_id}")
        
        op.campaign_id = campaign_id
        op.alias = alias
        op.stage = "streams_creation"
        db.commit()

        # Поток 1: forced (Google)
        stream1 = await keitaro.create_stream({
            "campaign_id": campaign_id,
            "name": "Forced Redirect (Google)",
            "position": 1,
            "type": "forced",
            "filter": {"type": "accept", "countries": request.excluded_countries},
            "redirect_url": "https://www.google.com/",
            "count_clicks": True
        })

        # Поток 2: default (offer)
        stream2 = await keitaro.create_stream({
            "campaign_id": campaign_id,
            "name": "Default Stream",
            "position": 2,
            "type": "default",
            "schema": {
                "offers": [{"offer_id": request.offer_id, "share": 100, "state": "active"}]
            },
            "count_clicks": True
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
            "domain_name": final_campaign.get("domain", {}).get("name"),
            "group_id": final_campaign.get("group_id"),
            "group_name": final_campaign.get("group", {}).get("name"),
            "traffic_source_id": final_campaign.get("traffic_source_id"),
            "traffic_source_name": final_campaign.get("traffic_source", {}).get("name"),
            "streams": streams.get("items", [])
        }

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
        "domain_name": campaign.get("domain", {}).get("name"),
        "group_id": campaign.get("group_id"),
        "group_name": campaign.get("group", {}).get("name"),
        "traffic_source_id": campaign.get("traffic_source_id"),
        "traffic_source_name": campaign.get("traffic_source", {}).get("name"),
        "streams": streams.get("items", [])
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
        
        current_revision = stream.get("revision", "")
        if current_revision != request.revision:
            raise HTTPException(status_code=409, detail="Revision mismatch")

        # Логика распределения (в KeitaroClient нужно будет реализовать расчет долей)
        # Здесь просто передаем офферы
        keitaro_update = {
            "offers": [{"offer_id": o.offer_id} for o in request.offers]
        }
        
        updated_stream = await keitaro.update_stream(stream_id, keitaro_update)
        
        op.status = "succeeded"
        db.commit()

        return {
            "offers": updated_stream.get("offers", []),
            "revision": updated_stream.get("revision", "new_revision")
        }

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
