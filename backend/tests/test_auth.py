from utils.auth import hash_password
from models import User


def test_register(test_client):
    response = test_client.post("/api/auth/register", json={
        "name": "New User",
        "email": "new@example.com",
        "password": "password123"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New User"
    assert data["email"] == "new@example.com"
    assert "id" in data


def test_register_duplicate_email(test_client, test_user):
    response = test_client.post("/api/auth/register", json={
        "name": "Another User",
        "email": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 400


def test_login_success(test_client, test_user):
    response = test_client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user_name"] == "Test User"


def test_login_wrong_password(test_client, test_user):
    response = test_client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401


def test_login_nonexistent_user(test_client):
    response = test_client.post("/api/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "password"
    })
    assert response.status_code == 401


def test_get_me(test_client, test_user, auth_headers):
    response = test_client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"


def test_get_me_no_token(test_client):
    response = test_client.get("/api/auth/me")
    assert response.status_code in (401, 403)
