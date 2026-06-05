from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.db.base import Base
from app.db.session import engine, SessionLocal

# Setup a test database and TestClient
@pytest.fixture(scope="module")
def client():
    # Use SQLite in-memory for testing, or just the regular test db
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def test_user():
    return {
        "email": "test_user_99@example.com",
        "password": "SecurePassword123!"
    }

def test_health_check(client):
    """Test the monitoring health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "voicejournal-api"}

def test_register_user(client, test_user):
    """Test user registration"""
    response = client.post(
        "/api/v1/auth/register",
        json=test_user
    )
    assert response.status_code in [201, 409] # 409 if already exists from previous test run
    if response.status_code == 201:
        data = response.json()
        assert data["email"] == test_user["email"]
        assert "id" in data

def test_login_user(client, test_user):
    """Test user authentication and JWT generation"""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user["email"], "password": test_user["password"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_get_journals_unauthorized(client):
    """Test that protected endpoints reject unauthenticated requests"""
    response = client.get("/api/v1/journals/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_get_journals_authorized(client, test_user):
    """Test fetching journal entries with a valid JWT"""
    # Login first
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": test_user["email"], "password": test_user["password"]}
    )
    token = login_res.json()["access_token"]
    
    # Fetch journals
    response = client.get(
        "/api/v1/journals/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert "entries" in response.json()
    assert isinstance(response.json()["entries"], list)

def test_get_mood_trends(client, test_user):
    """Test the dashboard mood trends endpoint"""
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": test_user["email"], "password": test_user["password"]}
    )
    token = login_res.json()["access_token"]
    
    response = client.get(
        "/api/v1/journals/trends?days=30",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "average_valence" in data
    assert "most_common_emotion" in data
    assert "trends" in data
