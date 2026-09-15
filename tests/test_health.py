def test_health_endpoint(client):
    """Verify GET /health returns HTTP 200 with database status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["database"]["status"] == "connected"
    assert "sqlite" in data["database"]["engine"].lower()
    assert "redis" in data
    assert "url" not in data["redis"]
    assert data["version"] == "0.1.0"

def test_api_v1_health_endpoint(client):
    """Verify GET /api/v1/health alias endpoint returns HTTP 200."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["database"]["status"] == "connected"

def test_root_endpoint(client):
    """Verify root endpoint returns platform metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "MandiQ"
    assert data["status"] == "online"
