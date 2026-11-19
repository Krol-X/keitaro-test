import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime

import pycountry
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator

from app.database import get_db, init_db
from app.models import Operation, OfferShareLock
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
        return normalize_country_codes(v)

class UpdateCampaignRequest(BaseModel):
    name: Optional[str] = None
    state: Optional[str] = None
    domain_id: Optional[int] = None
    group_id: Optional[int] = None
    traffic_source_id: Optional[int] = None

    @validator("name")
    def update_name_not_empty(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Name cannot be empty")
        return value.strip() if value is not None else value

    @validator("state")
    def campaign_state_valid(cls, value):
        if value is not None and value not in {"active", "disabled"}:
            raise ValueError("State must be active or disabled")
        return value


class StreamOfferUpdate(BaseModel):
    offer_id: int
    share: int = Field(ge=0, le=100)
    state: str = "active"
    share_locked: Optional[bool] = None

    @validator("state")
    def valid_state(cls, value):
        if value not in {"active", "disabled"}:
            raise ValueError("Offer state must be active or disabled")
        return value

class StreamOffersRequest(BaseModel):
    offers: List[StreamOfferUpdate]


class UpdateFilterCountriesRequest(BaseModel):
    excluded_countries: List[str]

    @validator("excluded_countries")
    def countries_valid(cls, v):
        return normalize_country_codes(v)

# --- Помощники ---

def hash_request(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def normalize_country_codes(codes: List[str]) -> List[str]:
    normalized = sorted({code.strip().upper() for code in codes if code.strip()})
    invalid = [code for code in normalized if pycountry.countries.get(alpha_2=code) is None]
    if invalid:
        raise ValueError(f"Unknown country codes: {', '.join(invalid)}")
    return normalized


COUNTRY_FILTER_NAMES = {"country", "countries"}
REDIRECT_STREAM_NAME = "Forced Redirect (Google)"
REDIRECT_PAYLOAD = "https://www.google.com/"


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
        for offer in item["offers"] or []:
            offer.setdefault("share_locked", False)
        streams.append(item)
    return streams


def apply_offer_share_locks(streams: List[Dict[str, Any]], campaign_id: int, db: Session) -> List[Dict[str, Any]]:
    stream_ids = [stream.get("stream_id") for stream in streams]
    locks = db.query(OfferShareLock).filter(
        OfferShareLock.campaign_id == campaign_id,
        OfferShareLock.stream_id.in_(stream_ids or [-1]),
        OfferShareLock.share_locked.is_(True),
    ).all()
    locked_keys = {(lock.stream_id, lock.offer_id) for lock in locks}
    for stream in streams:
        for offer in stream.get("offers") or []:
            offer["share_locked"] = (stream.get("stream_id"), offer.get("offer_id")) in locked_keys
    return streams


def stream_country_filter(stream: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for stream_filter in stream.get("filters") or []:
        if isinstance(stream_filter, dict) and str(stream_filter.get("name", "")).casefold() in COUNTRY_FILTER_NAMES:
            return stream_filter
    return None


def find_redirect_stream(streams: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pick the redirect flow we manage: prefers a flow already carrying a country filter."""
    forced = [stream for stream in streams if stream.get("type") == "forced"]
    candidates = [stream for stream in forced if stream_country_filter(stream) is not None] or forced
    return min(candidates, key=lambda stream: stream.get("position") or 0) if candidates else None


async def resolve_country_filter_name() -> str:
    stream_filters = response_items(await keitaro.list_stream_filters())
    country_filter = next(
        (item for item in stream_filters if str(item.get("value", "")).casefold() in COUNTRY_FILTER_NAMES),
        None,
    )
    if country_filter is None:
        raise HTTPException(status_code=502, detail="Keitaro does not expose a country stream filter")
    return country_filter["value"]


def decorate_streams(streams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Expose a normalized country filter per stream so the UI can render and edit it."""
    for stream in streams:
        stream_filter = stream_country_filter(stream)
        payload = stream_filter.get("payload") if stream_filter else None
        if isinstance(payload, str):
            payload = [code for code in re.split(r"[,\s]+", payload) if code]
        stream["country_filter"] = {
            "name": stream_filter.get("name"),
            "mode": stream_filter.get("mode"),
            "countries": sorted({str(code).upper() for code in payload or []}),
        } if stream_filter else None
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
        {"code": country.alpha_2, "name": country.name}
        for country in sorted(pycountry.countries, key=lambda item: item.name.casefold())
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

        if request.excluded_countries:
            country_filter_name = await resolve_country_filter_name()
            await keitaro.create_stream({
                "campaign_id": campaign_id,
                "name": REDIRECT_STREAM_NAME,
                "position": 1,
                "type": "forced",
                "schema": "redirect",
                "action_type": "http",
                "action_payload": REDIRECT_PAYLOAD,
                "collect_clicks": True,
                "filters": [{
                    "name": country_filter_name,
                    "mode": "accept",
                    "payload": request.excluded_countries,
                }],
            })

        await keitaro.create_stream({
            "campaign_id": campaign_id,
            "name": "Default Stream",
            "position": 2 if request.excluded_countries else 1,
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
async def get_campaign_detail(campaign_id: int, db: Session = Depends(get_db)):
    campaign = await keitaro.get_campaign(campaign_id)
    streams = decorate_streams(
        apply_offer_share_locks(normalize_streams(await keitaro.list_streams(campaign_id)), campaign_id, db)
    )

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

@router.put("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: int, request: UpdateCampaignRequest):
    changes = request.dict(exclude_unset=True)
    requested_state = changes.pop("state", None)
    if not changes and requested_state is None:
        raise HTTPException(status_code=400, detail="Provide at least one campaign field to update")
    try:
        if changes:
            await keitaro.update_campaign(campaign_id, changes)
        if requested_state == "active":
            await keitaro.enable_campaign(campaign_id)
        elif requested_state == "disabled":
            await keitaro.disable_campaign(campaign_id)
        updated = await keitaro.get_campaign(campaign_id)
        return {
            "campaign_id": updated["id"],
            "name": updated["name"],
            "state": updated["state"],
            "campaign_url": updated.get("url"),
            "domain_id": updated.get("domain_id"),
            "domain_name": related_name(updated.get("domain")),
            "group_id": updated.get("group_id"),
            "group_name": related_name(updated.get("group")),
            "traffic_source_id": updated.get("traffic_source_id"),
            "traffic_source_name": related_name(updated.get("traffic_source")),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/campaigns/{campaign_id}", status_code=204)
async def delete_campaign(campaign_id: int):
    try:
        await keitaro.delete_campaign(campaign_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


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

        submitted = {offer.offer_id: offer for offer in request.offers}
        if len(submitted) != len(request.offers):
            raise HTTPException(status_code=422, detail="Duplicate offer IDs are not allowed")

        persisted_locks = db.query(OfferShareLock).filter(
            OfferShareLock.campaign_id == campaign_id,
            OfferShareLock.stream_id == stream_id,
            OfferShareLock.share_locked.is_(True),
        ).all()
        stream_offers = {int(offer.get("offer_id")): offer for offer in stream.get("offers", [])}
        new_offer_ids = set(submitted) - set(stream_offers)
        if new_offer_ids:
            available_offers = response_items(await keitaro.list_offers())
            valid_offer_ids = {int(offer["id"]) for offer in available_offers if offer.get("id") is not None}
            unknown_ids = sorted(new_offer_ids - valid_offer_ids)
            if unknown_ids:
                raise HTTPException(status_code=422, detail=f"Offer not found: {', '.join(map(str, unknown_ids))}")

        for lock in persisted_locks:
            submitted_offer = submitted.get(lock.offer_id)
            current_offer = stream_offers.get(lock.offer_id)
            if submitted_offer is None:
                raise HTTPException(status_code=409, detail=f"Locked offer {lock.offer_id} cannot be removed")
            current_share = int((current_offer or {}).get("share", 0))
            if submitted_offer.share != current_share and submitted_offer.share_locked is not False:
                raise HTTPException(status_code=409, detail=f"Offer {lock.offer_id} share is locked; unlock it before changing the percentage")

        keitaro_update = {
            "offers": [offer.dict(exclude={"share_locked"}) for offer in request.offers]
        }
        updated_stream = await keitaro.update_stream(stream_id, keitaro_update)

        for offer in request.offers:
            if offer.share_locked is None:
                continue
            lock = db.query(OfferShareLock).filter_by(
                campaign_id=campaign_id, stream_id=stream_id, offer_id=offer.offer_id
            ).first()
            if offer.share_locked:
                if lock is None:
                    db.add(OfferShareLock(
                        campaign_id=campaign_id,
                        stream_id=stream_id,
                        offer_id=offer.offer_id,
                        share_locked=True,
                    ))
                else:
                    lock.share_locked = True
            elif lock is not None:
                db.delete(lock)

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


@router.put("/campaigns/{campaign_id}/country-filter")
async def update_country_filter(
    campaign_id: int,
    request: UpdateFilterCountriesRequest,
    db: Session = Depends(get_db)
):
    """Add, change or clear the excluded-country filter of the campaign's redirect flow."""
    op = Operation(type="update_country_filter", status="running", stage="validation", campaign_id=campaign_id)
    db.add(op)
    db.commit()

    try:
        current_streams = normalize_streams(await keitaro.list_streams(campaign_id))
        redirect_stream = find_redirect_stream(current_streams)
        countries = request.excluded_countries
        stream_id = int(redirect_stream["stream_id"]) if redirect_stream is not None else None
        op.stream_id = stream_id

        if not countries:
            removed = False
            current_filter = stream_country_filter(redirect_stream) if redirect_stream is not None else None
            if redirect_stream is not None and current_filter is not None:
                other_filters = [
                    item for item in redirect_stream.get("filters") or []
                    if isinstance(item, dict) and item is not current_filter
                ]
                if other_filters:
                    await keitaro.update_stream(stream_id, {"filters": other_filters})
                else:
                    await keitaro.disable_stream(stream_id)
                    removed = True
            op.status = "succeeded"
            op.stage = "completed"
            db.commit()
            return {
                "excluded_countries": [],
                "removed": removed,
                "streams": decorate_streams(normalize_streams(await keitaro.list_streams(campaign_id))),
            }

        if redirect_stream is None:
            country_filter_name = await resolve_country_filter_name()
            default_positions = [int(s.get("position") or 0) for s in current_streams if s.get("type") == "default"]
            position = min(default_positions) if default_positions else 1
            created = await keitaro.create_stream({
                "campaign_id": campaign_id,
                "name": REDIRECT_STREAM_NAME,
                "position": position,
                "type": "forced",
                "schema": "redirect",
                "action_type": "http",
                "action_payload": REDIRECT_PAYLOAD,
                "collect_clicks": True,
                "filters": [{"name": country_filter_name, "mode": "accept", "payload": countries}],
            })
            op.stream_id = int((created or {}).get("id") or 0) or None
            for default_stream in current_streams:
                if default_stream.get("type") == "default" and int(default_stream.get("position") or 0) >= position:
                    await keitaro.update_stream(int(default_stream["stream_id"]), {
                        "position": int(default_stream.get("position") or 0) + 1,
                    })
        else:
            current_filter = stream_country_filter(redirect_stream)
            filter_payload = {
                "name": current_filter.get("name") if current_filter else await resolve_country_filter_name(),
                "mode": "accept",
                "payload": countries,
            }
            if current_filter is not None and current_filter.get("id") is not None:
                filter_payload["id"] = current_filter["id"]
            kept_filters = [
                item for item in redirect_stream.get("filters") or []
                if isinstance(item, dict) and item is not current_filter
            ]
            await keitaro.update_stream(stream_id, {
                "name": redirect_stream.get("name") or REDIRECT_STREAM_NAME,
                "type": "forced",
                "schema": redirect_stream.get("schema") or "redirect",
                "filters": [*kept_filters, filter_payload],
            })
            if redirect_stream.get("state") == "disabled":
                await keitaro.enable_stream(stream_id)

        op.status = "succeeded"
        op.stage = "completed"
        db.commit()
        return {
            "excluded_countries": countries,
            "removed": False,
            "streams": decorate_streams(normalize_streams(await keitaro.list_streams(campaign_id))),
        }

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
