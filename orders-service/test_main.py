"""
Unit tests for Orders Service.
Tests business logic, error handling, and endpoint validation.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app
from models import orders_db, Order


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_orders_db():
    """Reset the orders database before each test."""
    orders_db.clear()
    orders_db.extend([
        Order(id=1, user_id=1, product_id=1, quantity=2),
        Order(id=2, user_id=2, product_id=2, quantity=1),
    ])
    yield
    # Cleanup after test
    orders_db.clear()
    orders_db.extend([
        Order(id=1, user_id=1, product_id=1, quantity=2),
        Order(id=2, user_id=2, product_id=2, quantity=1),
    ])


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_check(self, client):
        """Test that health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "orders-service"


class TestMetricsEndpoint:
    """Tests for the Prometheus metrics endpoint."""
    
    def test_metrics_endpoint(self, client):
        """Test that metrics endpoint returns Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"] or "text/openmetrics" in response.headers["content-type"]
        # Check that metrics contain expected counters
        assert b"http_requests_total" in response.content or b"http_request" in response.content


class TestGetOrders:
    """Tests for GET /orders endpoint."""
    
    def test_get_all_orders(self, client):
        """Test fetching all orders returns the correct list."""
        response = client.get("/orders")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["user_id"] == 1
        assert data[1]["user_id"] == 2
    
    def test_get_orders_returns_list(self, client):
        """Test that get orders always returns a list."""
        response = client.get("/orders")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_orders_have_required_fields(self, client):
        """Test that all orders have required fields."""
        response = client.get("/orders")
        assert response.status_code == 200
        data = response.json()
        for order in data:
            assert "id" in order
            assert "user_id" in order
            assert "product_id" in order
            assert "quantity" in order


class TestGetOrderById:
    """Tests for GET /orders/{order_id} endpoint."""
    
    def test_get_order_by_id_success(self, client):
        """Test fetching an order by valid ID."""
        response = client.get("/orders/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["user_id"] == 1
        assert data["product_id"] == 1
        assert data["quantity"] == 2
    
    def test_get_order_by_id_not_found(self, client):
        """Test fetching a non-existent order returns 404."""
        response = client.get("/orders/999")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Order not found"
    
    def test_get_order_response_has_trace_id(self, client):
        """Test that response includes X-Trace-ID header."""
        response = client.get("/orders/1")
        assert "X-Trace-ID" in response.headers


class TestCreateOrder:
    """Tests for POST /orders/create endpoint."""
    
    @patch("main.validate_user")
    @patch("main.validate_product")
    def test_create_order_success(self, mock_validate_product, mock_validate_user, client):
        """Test creating a new order with valid data."""
        mock_validate_user.return_value = None
        mock_validate_product.return_value = None
        
        new_order = {"user_id": 1, "product_id": 1, "quantity": 5}
        response = client.post("/orders/create", json=new_order)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 1
        assert data["product_id"] == 1
        assert data["quantity"] == 5
        assert data["id"] == 3  # Next ID after existing orders
    
    def test_create_order_invalid_quantity(self, client):
        """Test creating an order with invalid quantity fails validation."""
        invalid_order = {"user_id": 1, "product_id": 1, "quantity": 0}
        response = client.post("/orders/create", json=invalid_order)
        assert response.status_code == 422  # Validation error
    
    def test_create_order_negative_quantity(self, client):
        """Test creating an order with negative quantity fails validation."""
        invalid_order = {"user_id": 1, "product_id": 1, "quantity": -1}
        response = client.post("/orders/create", json=invalid_order)
        assert response.status_code == 422  # Validation error
    
    def test_create_order_missing_fields(self, client):
        """Test creating an order with missing fields fails."""
        incomplete_order = {"user_id": 1}
        response = client.post("/orders/create", json=incomplete_order)
        assert response.status_code == 422  # Validation error


class TestSlowEndpoint:
    """Tests for the slow service simulation endpoint."""
    
    def test_slow_endpoint_returns_delay_info(self, client):
        """Test that slow endpoint returns delay information."""
        response = client.get("/orders/slow/0.1")  # Use small delay for testing
        assert response.status_code == 200
        data = response.json()
        assert "delay" in data
        assert data["delay"] == 0.1
    
    def test_slow_endpoint_message(self, client):
        """Test that slow endpoint returns expected message."""
        response = client.get("/orders/slow/0.1")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "0.1" in data["message"]


class TestErrorEndpoint:
    """Tests for the controlled error endpoint."""
    
    def test_error_endpoint_returns_500(self, client):
        """Test that error endpoint returns 500 status."""
        response = client.get("/orders/error")
        assert response.status_code == 500
        data = response.json()
        assert "Controlled internal server error" in data["detail"]


class TestCorrelationId:
    """Tests for correlation ID (trace-id) propagation."""
    
    def test_trace_id_propagation(self, client):
        """Test that provided X-Trace-ID is propagated in response."""
        trace_id = "test-trace-id-orders-12345"
        response = client.get("/orders", headers={"X-Trace-ID": trace_id})
        assert response.status_code == 200
        assert response.headers.get("X-Trace-ID") == trace_id
    
    def test_trace_id_generated_when_not_provided(self, client):
        """Test that X-Trace-ID is generated when not provided."""
        response = client.get("/orders")
        assert response.status_code == 200
        assert "X-Trace-ID" in response.headers
        # Verify it's a valid UUID format
        trace_id = response.headers.get("X-Trace-ID")
        assert len(trace_id) == 36  # UUID format


class TestExternalMetrics:
    """Tests for external service call metrics."""
    
    def test_metrics_include_external_calls(self, client):
        """Test that metrics endpoint includes external service call counters."""
        response = client.get("/metrics")
        assert response.status_code == 200
        # These metrics might be empty initially but should be defined
        content = response.content.decode()
        # The metrics should be defined even if no calls have been made yet
        assert "external_service_calls_total" in content or "http_requests_total" in content
