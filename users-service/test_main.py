"""
Unit tests for Users Service.
Tests business logic, error handling, and endpoint validation.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app
from models import users_db, User


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_users_db():
    """Reset the users database before each test."""
    users_db.clear()
    users_db.extend([
        User(id=1, name="Alice", email="alice@example.com"),
        User(id=2, name="Bob", email="bob@example.com"),
    ])
    yield
    # Cleanup after test
    users_db.clear()
    users_db.extend([
        User(id=1, name="Alice", email="alice@example.com"),
        User(id=2, name="Bob", email="bob@example.com"),
    ])


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_check(self, client):
        """Test that health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "users-service"


class TestMetricsEndpoint:
    """Tests for the Prometheus metrics endpoint."""
    
    def test_metrics_endpoint(self, client):
        """Test that metrics endpoint returns Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"] or "text/openmetrics" in response.headers["content-type"]
        # Check that metrics contain expected counters
        assert b"http_requests_total" in response.content or b"http_request" in response.content


class TestGetUsers:
    """Tests for GET /users endpoint."""
    
    def test_get_all_users(self, client):
        """Test fetching all users returns the correct list."""
        response = client.get("/users")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Alice"
        assert data[1]["name"] == "Bob"
    
    def test_get_users_returns_list(self, client):
        """Test that get users always returns a list."""
        response = client.get("/users")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestGetUserById:
    """Tests for GET /users/{user_id} endpoint."""
    
    def test_get_user_by_id_success(self, client):
        """Test fetching a user by valid ID."""
        response = client.get("/users/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Alice"
        assert data["email"] == "alice@example.com"
    
    def test_get_user_by_id_not_found(self, client):
        """Test fetching a non-existent user returns 404."""
        response = client.get("/users/999")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "User not found"
    
    def test_get_user_response_has_trace_id(self, client):
        """Test that response includes X-Trace-ID header."""
        response = client.get("/users/1")
        assert "X-Trace-ID" in response.headers


class TestCreateUser:
    """Tests for POST /users/create endpoint."""
    
    def test_create_user_success(self, client):
        """Test creating a new user with valid data."""
        new_user = {"name": "Charlie", "email": "charlie@example.com"}
        response = client.post("/users/create", json=new_user)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Charlie"
        assert data["email"] == "charlie@example.com"
        assert data["id"] == 3  # Next ID after existing users
    
    def test_create_user_duplicate_email(self, client):
        """Test creating a user with duplicate email returns 400."""
        duplicate_user = {"name": "Alice Clone", "email": "alice@example.com"}
        response = client.post("/users/create", json=duplicate_user)
        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "Email already registered"
    
    def test_create_user_invalid_email(self, client):
        """Test creating a user with invalid email format."""
        invalid_user = {"name": "Invalid", "email": "not-an-email"}
        response = client.post("/users/create", json=invalid_user)
        assert response.status_code == 422  # Validation error


class TestSlowEndpoint:
    """Tests for the slow service simulation endpoint."""
    
    def test_slow_endpoint_returns_delay_info(self, client):
        """Test that slow endpoint returns delay information."""
        response = client.get("/users/slow/0.1")  # Use small delay for testing
        assert response.status_code == 200
        data = response.json()
        assert "delay" in data
        assert data["delay"] == 0.1


class TestErrorEndpoint:
    """Tests for the controlled error endpoint."""
    
    def test_error_endpoint_returns_500(self, client):
        """Test that error endpoint returns 500 status."""
        response = client.get("/users/error")
        assert response.status_code == 500
        data = response.json()
        assert "Controlled internal server error" in data["detail"]


class TestCorrelationId:
    """Tests for correlation ID (trace-id) propagation."""
    
    def test_trace_id_propagation(self, client):
        """Test that provided X-Trace-ID is propagated in response."""
        trace_id = "test-trace-id-12345"
        response = client.get("/users", headers={"X-Trace-ID": trace_id})
        assert response.status_code == 200
        assert response.headers.get("X-Trace-ID") == trace_id
    
    def test_trace_id_generated_when_not_provided(self, client):
        """Test that X-Trace-ID is generated when not provided."""
        response = client.get("/users")
        assert response.status_code == 200
        assert "X-Trace-ID" in response.headers
        # Verify it's a valid UUID format
        trace_id = response.headers.get("X-Trace-ID")
        assert len(trace_id) == 36  # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
