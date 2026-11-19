import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import engine, Base
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
