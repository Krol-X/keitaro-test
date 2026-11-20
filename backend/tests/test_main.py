import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.database import engine, Base, SessionLocal
from app.models import OfferShareLock
from unittest.mock import patch, AsyncMock

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@patch("app.routers.campaigns.keitaro.list_traffic_sources")
@patch("app.routers.campaigns.keitaro.list_groups")
@patch("app.routers.campaigns.keitaro.list_campaigns")
def test_list_campaigns(mock_list, mock_groups, mock_sources):
    mock_groups.return_value = []
    mock_sources.return_value = []
    mock_list.return_value = {
        "items": [{"id": 123, "name": "Летняя акция", "group": {"name": "Основная"}, "traffic_source": {"name": "Источник"}, "state": "active"}]
    }
    response = client.get("/api/v1/campaigns")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["campaign_id"] == 123
    assert data["items"][0]["name"] == "Летняя акция"

@patch("app.routers.campaigns.keitaro.list_traffic_sources")
@patch("app.routers.campaigns.keitaro.list_groups")
@patch("app.routers.campaigns.keitaro.list_campaigns")
def test_list_campaigns_accepts_keitaro_array_response(mock_list, mock_groups, mock_sources):
    mock_groups.return_value = []
    mock_sources.return_value = []
    mock_list.return_value = [
        {
            "id": 123,
            "name": "Летняя акция",
            "group": [{"name": "Основная"}],
            "traffic_source": {"name": "Источник"},
            "state": "active",
        }
    ]

    response = client.get("/api/v1/campaigns")

    assert response.status_code == 200
    assert response.json()["items"][0]["group_name"] == "Основная"

@patch("app.routers.campaigns.keitaro.list_traffic_sources")
@patch("app.routers.campaigns.keitaro.list_groups")
@patch("app.routers.campaigns.keitaro.list_domains")
def test_references_include_full_country_list(mock_domains, mock_groups, mock_sources):
    mock_domains.return_value = []
    mock_groups.return_value = []
    mock_sources.return_value = []

    response = client.get("/api/v1/references")

    assert response.status_code == 200
    countries = response.json()["countries"]
    assert len(countries) >= 240
    assert {"code": "BY", "name": "Belarus"} in countries
    assert {"code": "US", "name": "United States"} in countries

@patch("app.routers.campaigns.keitaro.get_campaign", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.disable_campaign", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.update_campaign", new_callable=AsyncMock)
def test_update_campaign_metadata_and_state(mock_update, mock_disable, mock_get):
    mock_update.return_value = {}
    mock_disable.return_value = {}
    mock_get.return_value = {
        "id": 123, "name": "Renamed", "state": "disabled", "group_id": 7,
        "group": {"name": "Group"}, "domain_id": 2, "traffic_source_id": 3
    }

    response = client.put("/api/v1/campaigns/123", json={
        "name": "Renamed", "state": "disabled", "group_id": 7
    })

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    assert response.json()["state"] == "disabled"
    mock_update.assert_awaited_once_with(123, {"name": "Renamed", "group_id": 7})
    mock_disable.assert_awaited_once_with(123)
    mock_get.assert_awaited_once_with(123)

@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.get_stream", new_callable=AsyncMock)
def test_update_offer_percentage_and_persist_lock(mock_get_stream, mock_update_stream):
    original = {
        "id": 12, "campaign_id": 50, "name": "Offers", "position": 2, "type": "default", "schema": "landings",
        "offers": [{"offer_id": 8, "share": 35, "state": "active"}]
    }
    # Второй вызов — сверка после PUT, оффер уже с новой долей.
    mock_get_stream.side_effect = [
        original,
        {**original, "offers": [{"offer_id": 8, "share": 45, "state": "active"}]},
    ]
    mock_update_stream.return_value = {"offers": [{"offer_id": 8, "share": 45, "state": "active"}]}

    response = client.put("/api/v1/campaigns/50/streams/12/offers", json={
        "offers": [{"offer_id": 8, "share": 45, "state": "active", "share_locked": True}]
    })

    assert response.status_code == 200
    sent_offer = mock_update_stream.call_args.args[1]["offers"][0]
    assert sent_offer == {"offer_id": 8, "share": 45, "state": "active"}
    db = SessionLocal()
    try:
        lock = db.query(OfferShareLock).filter_by(campaign_id=50, stream_id=12, offer_id=8).one()
        assert lock.share_locked is True
    finally:
        db.close()

@patch("app.routers.campaigns.keitaro.list_offers", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.get_stream", new_callable=AsyncMock)
def test_add_offer_to_existing_stream(mock_get_stream, mock_update_stream, mock_list_offers):
    original = {
        "id": 12, "campaign_id": 50, "name": "Offers", "position": 2, "type": "default", "schema": "landings",
        "offers": [{"offer_id": 8, "share": 100, "state": "active"}]
    }
    updated = {
        **original,
        "offers": [{"offer_id": 8, "share": 50, "state": "active"}, {"offer_id": 9, "share": 50, "state": "active"}],
    }
    mock_get_stream.side_effect = [original, updated]
    mock_list_offers.return_value = [{"id": 9, "name": "New offer"}]
    mock_update_stream.return_value = updated

    response = client.put("/api/v1/campaigns/50/streams/12/offers", json={
        "offers": [
            {"offer_id": 8, "share": 50, "state": "active"},
            {"offer_id": 9, "share": 50, "state": "active"},
        ]
    })

    assert response.status_code == 200
    mock_list_offers.assert_awaited_once()
    sent_ids = {offer["offer_id"] for offer in mock_update_stream.call_args.args[1]["offers"]}
    assert sent_ids == {8, 9}

@patch("app.routers.campaigns.keitaro.list_offers", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.get_stream", new_callable=AsyncMock)
def test_reject_adding_unknown_offer(mock_get_stream, mock_update_stream, mock_list_offers):
    mock_get_stream.return_value = {
        "id": 12, "campaign_id": 50,
        "offers": [{"offer_id": 8, "share": 100, "state": "active"}]
    }
    mock_list_offers.return_value = [{"id": 9, "name": "New offer"}]

    response = client.put("/api/v1/campaigns/50/streams/12/offers", json={
        "offers": [
            {"offer_id": 8, "share": 50, "state": "active"},
            {"offer_id": 99, "share": 50, "state": "active"},
        ]
    })

    assert response.status_code == 422
    mock_update_stream.assert_not_awaited()

@patch("app.routers.campaigns.keitaro.get_stream", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
def test_locked_offer_percentage_cannot_change_without_unlock(mock_update_stream, mock_get_stream):
    db = SessionLocal()
    db.add(OfferShareLock(campaign_id=50, stream_id=12, offer_id=8, share_locked=True))
    db.commit()
    db.close()
    mock_get_stream.return_value = {
        "id": 12, "campaign_id": 50,
        "offers": [{"offer_id": 8, "share": 45, "state": "active"}]
    }

    response = client.put("/api/v1/campaigns/50/streams/12/offers", json={
        "offers": [{"offer_id": 8, "share": 55, "state": "active", "share_locked": True}]
    })

    assert response.status_code == 409
    mock_update_stream.assert_not_awaited()

@patch("app.routers.campaigns.keitaro.list_streams", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.get_campaign", new_callable=AsyncMock)
def test_campaign_detail_includes_persisted_offer_lock(mock_get_campaign, mock_list_streams):
    db = SessionLocal()
    db.add(OfferShareLock(campaign_id=50, stream_id=12, offer_id=8, share_locked=True))
    db.commit()
    db.close()
    mock_get_campaign.return_value = {"id": 50, "name": "Test", "state": "active"}
    mock_list_streams.return_value = [{
        "id": 12, "type": "default",
        "offers": [{"offer_id": 8, "share": 45, "state": "disabled"}]
    }]

    response = client.get("/api/v1/campaigns/50")

    assert response.status_code == 200
    assert response.json()["streams"][0]["offers"][0]["share_locked"] is True

@patch("app.routers.campaigns.keitaro.delete_campaign", new_callable=AsyncMock)
def test_delete_campaign(mock_delete):
    response = client.delete("/api/v1/campaigns/123")

    assert response.status_code == 204
    mock_delete.assert_awaited_once_with(123)

@patch("app.routers.campaigns.keitaro.list_stream_filters")
@patch("app.routers.campaigns.keitaro.create_campaign")
@patch("app.routers.campaigns.keitaro.list_offers")
@patch("app.routers.campaigns.keitaro.create_stream")
@patch("app.routers.campaigns.keitaro.enable_campaign")
@patch("app.routers.campaigns.keitaro.get_campaign")
@patch("app.routers.campaigns.keitaro.list_streams")
def test_create_campaign(mock_list_streams, mock_get, mock_enable, mock_stream, mock_offers, mock_create, mock_filters):
    mock_offers.return_value = [{"id": 42, "name": "Offer"}]
    mock_filters.return_value = [{"value": "country", "modes": {"accept": "accept", "reject": "reject"}}]
    mock_create.return_value = {"id": 101, "alias": "cmp_101", "state": "disabled"}
    mock_stream.side_effect = [{"id": 201}, {"id": 202}]
    mock_enable.return_value = {}
    mock_get.return_value = {"id": 101, "name": "Test", "state": "active", "url": "http://test.com", "domain_id": 1, "domain": {"name": "D"}, "group_id": 2, "group": {"name": "G"}, "traffic_source_id": 3, "traffic_source": {"name": "T"}}
    mock_list_streams.return_value = [{"id": 201}, {"id": 202}]

    headers = {"Idempotency-Key": "key-123"}
    payload = {
        "name": "Летняя акция",
        "excluded_countries": ["PL", "LT"],
        "offer_id": 42,
        "domain_id": 1,
        "group_id": 2,
        "traffic_source_id": 3
    }
    
    response = client.post("/api/v1/campaigns", json=payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["campaign_id"] == 101
    assert response.json()["state"] == "active"

    campaign_payload = mock_create.call_args.args[0]
    assert campaign_payload["alias"].startswith("campaign-")
    assert campaign_payload["domain_id"] == 1
    forced_payload, default_payload = [call.args[0] for call in mock_stream.call_args_list]
    assert forced_payload["schema"] == "redirect"
    assert forced_payload["action_payload"] == "https://www.google.com/"
    assert forced_payload["filters"] == [{"name": "country", "mode": "accept", "payload": ["LT", "PL"]}]
    assert default_payload["schema"] == "landings"
    assert default_payload["offers"] == [{"offer_id": 42, "share": 100, "state": "active"}]

@patch("app.routers.campaigns.keitaro.list_streams", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
def test_update_country_filter_replaces_countries(mock_update_stream, mock_list_streams):
    mock_list_streams.return_value = [
        {"id": 201, "campaign_id": 50, "type": "forced", "position": 1,
         "filters": [{"id": 33, "name": "country", "mode": "accept", "payload": ["PL", "LT"]}]},
        {"id": 202, "campaign_id": 50, "type": "default", "position": 2,
         "offers": [{"offer_id": 8, "share": 100, "state": "active"}]},
    ]
    mock_update_stream.return_value = {}

    response = client.put("/api/v1/campaigns/50/country-filter", json={
        "excluded_countries": ["by", "RU"]
    })

    assert response.status_code == 200
    assert response.json()["excluded_countries"] == ["BY", "RU"]
    sent_stream_id, sent_payload = mock_update_stream.call_args.args
    assert sent_stream_id == 201
    assert sent_payload["filters"] == [{"id": 33, "name": "country", "mode": "accept", "payload": ["BY", "RU"]}]
    assert sent_payload["type"] == "forced"


@patch("app.routers.campaigns.keitaro.list_streams", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.enable_stream", new_callable=AsyncMock)
def test_update_country_filter_reenables_disabled_redirect_stream(mock_enable_stream, mock_update_stream, mock_list_streams):
    mock_list_streams.return_value = [
        {"id": 201, "campaign_id": 50, "type": "forced", "position": 1, "state": "disabled",
         "filters": [{"name": "country", "mode": "accept", "payload": ["PL"]}]},
        {"id": 202, "campaign_id": 50, "type": "default", "position": 2, "offers": []},
    ]

    response = client.put("/api/v1/campaigns/50/country-filter", json={"excluded_countries": ["LT"]})

    assert response.status_code == 200
    mock_enable_stream.assert_awaited_once_with(201)


@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.list_streams", new_callable=AsyncMock)
def test_update_country_filter_creates_redirect_stream(mock_list_streams, mock_update_stream):
    streams = [{"id": 202, "campaign_id": 50, "type": "default", "position": 1,
                "offers": [{"offer_id": 8, "share": 100, "state": "active"}]}]
    mock_list_streams.side_effect = [streams, streams]
    created = {}

    async def fake_create_stream(payload):
        created.update(payload)
        return {"id": 300}

    with patch("app.routers.campaigns.keitaro.create_stream", new=fake_create_stream), \
         patch("app.routers.campaigns.keitaro.list_stream_filters", new_callable=AsyncMock,
               return_value=[{"value": "country", "modes": {"accept": "accept"}}]):
        response = client.put("/api/v1/campaigns/50/country-filter", json={"excluded_countries": ["BY"]})

    assert response.status_code == 200
    assert created["type"] == "forced"
    assert created["position"] == 1
    assert created["filters"] == [{"name": "country", "mode": "accept", "payload": ["BY"]}]
    assert mock_update_stream.await_args.args[0] == 202
    assert mock_update_stream.await_args.args[1] == {"position": 2}


@patch("app.routers.campaigns.keitaro.list_streams", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.disable_stream", new_callable=AsyncMock)
def test_update_country_filter_clears_filter_when_list_empty(mock_disable_stream, mock_list_streams):
    mock_list_streams.return_value = [
        {"id": 201, "campaign_id": 50, "type": "forced", "position": 1,
         "filters": [{"name": "country", "mode": "accept", "payload": ["PL"]}]},
        {"id": 202, "campaign_id": 50, "type": "default", "position": 2, "offers": []},
    ]

    response = client.put("/api/v1/campaigns/50/country-filter", json={"excluded_countries": []})

    assert response.status_code == 200
    assert response.json()["excluded_countries"] == []
    assert response.json()["removed"] is True
    mock_disable_stream.assert_awaited_once_with(201)


def test_update_country_filter_rejects_unknown_code():
    response = client.put("/api/v1/campaigns/50/country-filter", json={"excluded_countries": ["ZZ"]})

    assert response.status_code == 422


@patch("app.routers.campaigns.keitaro.get_campaign", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.list_streams", new_callable=AsyncMock)
def test_campaign_detail_exposes_country_filter(mock_list_streams, mock_get_campaign):
    mock_get_campaign.return_value = {"id": 50, "name": "Test", "state": "active"}
    mock_list_streams.return_value = [
        {"id": 201, "type": "forced", "position": 1,
         "filters": [{"id": 33, "name": "country", "mode": "accept", "payload": ["PL", "LT"]}]},
        {"id": 202, "type": "default", "position": 2, "offers": []},
    ]

    response = client.get("/api/v1/campaigns/50")

    assert response.status_code == 200
    forced, default = response.json()["streams"]
    assert forced["country_filter"] == {"name": "country", "mode": "accept", "countries": ["LT", "PL"]}
    assert default["country_filter"] is None

@patch("app.routers.campaigns.keitaro.list_stream_filters")
@patch("app.routers.campaigns.keitaro.list_streams")
@patch("app.routers.campaigns.keitaro.get_campaign")
@patch("app.routers.campaigns.keitaro.enable_campaign")
@patch("app.routers.campaigns.keitaro.create_stream")
@patch("app.routers.campaigns.keitaro.list_offers")
@patch("app.routers.campaigns.keitaro.create_campaign")
@patch("app.routers.campaigns.keitaro.update_stream")
def test_create_campaign_writes_filters_when_creation_drops_them(
    mock_update_stream, mock_create_campaign, mock_offers, mock_create_stream,
    mock_enable, mock_get_campaign, mock_list_streams, mock_filters
):
    mock_offers.return_value = [{"id": 42, "name": "Offer"}]
    mock_filters.return_value = [{"value": "country", "modes": {"accept": "accept", "reject": "reject"}}]
    mock_create_campaign.return_value = {"id": 101, "alias": "cmp_101", "state": "disabled"}
    # Keitaro вернул поток без вложенных filters — их нужно досоздать через PUT.
    mock_create_stream.side_effect = [{"id": 201, "filters": []}, {"id": 202}]
    mock_enable.return_value = {}
    mock_get_campaign.return_value = {"id": 101, "name": "Test", "state": "active"}
    mock_list_streams.return_value = [{"id": 201}, {"id": 202}]
    mock_update_stream.return_value = {}

    response = client.post("/api/v1/campaigns", json={
        "name": "Летняя акция",
        "excluded_countries": ["PL", "LT"],
        "offer_id": 42,
    }, headers={"Idempotency-Key": "key-filters"})

    assert response.status_code == 201
    mock_update_stream.assert_awaited_once_with(201, {
        "filters": [{"name": "country", "mode": "accept", "payload": ["LT", "PL"]}]
    })


@patch("app.routers.campaigns.keitaro.list_stream_filters")
@patch("app.routers.campaigns.keitaro.list_streams")
@patch("app.routers.campaigns.keitaro.get_campaign")
@patch("app.routers.campaigns.keitaro.enable_campaign")
@patch("app.routers.campaigns.keitaro.create_stream")
@patch("app.routers.campaigns.keitaro.list_offers")
@patch("app.routers.campaigns.keitaro.create_campaign")
@patch("app.routers.campaigns.keitaro.update_stream")
def test_create_campaign_skips_extra_put_when_filters_applied(
    mock_update_stream, mock_create_campaign, mock_offers, mock_create_stream,
    mock_enable, mock_get_campaign, mock_list_streams, mock_filters
):
    mock_offers.return_value = [{"id": 42, "name": "Offer"}]
    mock_filters.return_value = [{"value": "country", "modes": {"accept": "accept", "reject": "reject"}}]
    mock_create_campaign.return_value = {"id": 102, "alias": "cmp_102", "state": "disabled"}
    mock_create_stream.side_effect = [
        {"id": 211, "filters": [{"name": "country", "mode": "accept", "payload": ["PL"]}]},
        {"id": 212},
    ]
    mock_enable.return_value = {}
    mock_get_campaign.return_value = {"id": 102, "name": "Test", "state": "active"}
    mock_list_streams.return_value = [{"id": 211}, {"id": 212}]

    response = client.post("/api/v1/campaigns", json={
        "name": "Зимняя акция",
        "excluded_countries": ["PL"],
        "offer_id": 42,
    }, headers={"Idempotency-Key": "key-filters-ok"})

    assert response.status_code == 201
    mock_update_stream.assert_not_awaited()


@patch("app.routers.campaigns.keitaro.get_stream", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
def test_update_offers_sends_flow_identity_with_offers(mock_update_stream, mock_get_stream):
    """PUT /streams/{id} — полноценный документ потока, иначе Keitaro теряет схему и поток исчезает."""
    stream = {
        "id": 12, "campaign_id": 50, "name": "Offers", "position": 2,
        "type": "default", "schema": "landings", "state": "active",
        "filters": [{"id": 7, "name": "country", "mode": "accept", "payload": ["PL"]}],
        "offers": [{"offer_id": 8, "share": 100, "state": "active"}],
    }
    mock_get_stream.side_effect = [
        stream,
        {**stream, "offers": [{"offer_id": 8, "share": 100, "state": "active"}]},
    ]
    mock_update_stream.return_value = {}

    response = client.put("/api/v1/campaigns/50/streams/12/offers", json={
        "offers": [{"offer_id": 8, "share": 100, "state": "active"}]
    })

    assert response.status_code == 200
    sent = mock_update_stream.call_args.args[1]
    assert sent["name"] == "Offers"
    assert sent["position"] == 2
    assert sent["type"] == "default"
    assert sent["schema"] == "landings"
    assert sent["state"] == "active"
    # Гео-фильтр и прочие поля потока не должны слетать при сохранении офферов.
    assert sent["filters"] == [{"id": 7, "name": "country", "mode": "accept", "payload": ["PL"]}]
    assert [offer["offer_id"] for offer in sent["offers"]] == [8]


@patch("app.routers.campaigns.keitaro.get_stream", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
def test_update_offers_rejects_flow_without_active_offers(mock_update_stream, mock_get_stream):
    mock_get_stream.return_value = {
        "id": 12, "campaign_id": 50, "type": "default", "schema": "landings",
        "offers": [{"offer_id": 8, "share": 100, "state": "active"}],
    }

    response = client.put("/api/v1/campaigns/50/streams/12/offers", json={
        "offers": [{"offer_id": 8, "share": 0, "state": "disabled"}]
    })

    assert response.status_code == 409
    mock_update_stream.assert_not_awaited()


@patch("app.routers.campaigns.keitaro.get_stream", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
def test_update_offers_reports_flow_that_disappeared_after_update(mock_update_stream, mock_get_stream):
    mock_get_stream.side_effect = [
        {"id": 12, "campaign_id": 50, "type": "default", "schema": "landings",
         "offers": [{"offer_id": 8, "share": 100, "state": "active"}]},
        HTTPException(status_code=404, detail="Keitaro resource not found"),
    ]
    mock_update_stream.return_value = {}

    response = client.put("/api/v1/campaigns/50/streams/12/offers", json={
        "offers": [{"offer_id": 8, "share": 100, "state": "active"}]
    })

    assert response.status_code == 502
    assert "no longer returns flow 12" in response.json()["detail"]


@patch("app.routers.campaigns.keitaro.list_offers", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.get_stream", new_callable=AsyncMock)
@patch("app.routers.campaigns.keitaro.update_stream", new_callable=AsyncMock)
def test_update_offers_reports_offer_missing_after_update(mock_update_stream, mock_get_stream, mock_list_offers):
    mock_list_offers.return_value = [{"id": 8, "name": "A"}, {"id": 9, "name": "B"}]
    stream = {"id": 12, "campaign_id": 50, "type": "default", "schema": "landings",
              "offers": [{"offer_id": 8, "share": 100, "state": "active"}]}
    mock_get_stream.side_effect = [stream, {**stream, "offers": [{"offer_id": 8, "share": 100, "state": "active"}]}]
    mock_update_stream.return_value = {}

    response = client.put("/api/v1/campaigns/50/streams/12/offers", json={
        "offers": [{"offer_id": 8, "share": 50, "state": "active"},
                   {"offer_id": 9, "share": 50, "state": "active"}]
    })

    assert response.status_code == 502
    assert "did not store offers [9]" in response.json()["detail"]
