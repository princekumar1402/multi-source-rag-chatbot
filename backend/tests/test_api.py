import pytest
from starlette.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "project" in data
    assert data["api_v1"] == "/api/v1"

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "indexed_chunks" in data

def test_documents_list_empty():
    response = client.get("/api/v1/documents?workspace_id=test_empty_ws")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
