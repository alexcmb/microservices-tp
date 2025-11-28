"""
Unit tests for Products Service.
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
from models import products_db, Product


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_products_db():
    """Reset the products database before each test."""
    products_db.clear()
    products_db.extend([
        Product(id=1, name="Laptop", price=999.99),
        Product(id=2, name="Souris", price=29.99),
    ])
    yield
    # Cleanup after test
    products_db.clear()
    products_db.extend([
        Product(id=1, name="Laptop", price=999.99),
        Product(id=2, name="Souris", price=29.99),
    ])


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_check(self, client):
        """Test that health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "products-service"


class TestMetricsEndpoint:
    """Tests for the Prometheus metrics endpoint."""
    
    def test_metrics_endpoint(self, client):
        """Test that metrics endpoint returns Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"] or "text/openmetrics" in response.headers["content-type"]
        # Check that metrics contain expected counters
        assert b"http_requests_total" in response.content or b"http_request" in response.content


class TestGetProducts:
    """Tests for GET /products endpoint."""
    
    def test_get_all_products(self, client):
        """Test fetching all products returns the correct list."""
        response = client.get("/products")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Laptop"
        assert data[1]["name"] == "Souris"
    
    def test_get_products_returns_list(self, client):
        """Test that get products always returns a list."""
        response = client.get("/products")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_products_have_price(self, client):
        """Test that all products have price field."""
        response = client.get("/products")
        assert response.status_code == 200
        data = response.json()
        for product in data:
            assert "price" in product
            assert isinstance(product["price"], (int, float))


class TestGetProductById:
    """Tests for GET /products/{product_id} endpoint."""
    
    def test_get_product_by_id_success(self, client):
        """Test fetching a product by valid ID."""
        response = client.get("/products/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Laptop"
        assert data["price"] == 999.99
    
    def test_get_product_by_id_not_found(self, client):
        """Test fetching a non-existent product returns 404."""
        response = client.get("/products/999")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Product not found"
    
    def test_get_product_response_has_trace_id(self, client):
        """Test that response includes X-Trace-ID header."""
        response = client.get("/products/1")
        assert "X-Trace-ID" in response.headers


class TestCreateProduct:
    """Tests for POST /products/create endpoint."""
    
    def test_create_product_success(self, client):
        """Test creating a new product with valid data."""
        new_product = {"name": "Keyboard", "price": 149.99}
        response = client.post("/products/create", json=new_product)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Keyboard"
        assert data["price"] == 149.99
        assert data["id"] == 3  # Next ID after existing products
    
    def test_create_product_duplicate_name(self, client):
        """Test creating a product with duplicate name returns 400."""
        duplicate_product = {"name": "Laptop", "price": 1099.99}
        response = client.post("/products/create", json=duplicate_product)
        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "Product name already exists"
    
    def test_create_product_duplicate_name_case_insensitive(self, client):
        """Test that duplicate name check is case-insensitive."""
        duplicate_product = {"name": "LAPTOP", "price": 1099.99}
        response = client.post("/products/create", json=duplicate_product)
        assert response.status_code == 400
    
    def test_create_product_empty_name(self, client):
        """Test creating a product with empty name fails validation."""
        invalid_product = {"name": "", "price": 99.99}
        response = client.post("/products/create", json=invalid_product)
        assert response.status_code == 422  # Validation error


class TestSlowEndpoint:
    """Tests for the slow service simulation endpoint."""
    
    def test_slow_endpoint_returns_delay_info(self, client):
        """Test that slow endpoint returns delay information."""
        response = client.get("/products/slow/0.1")  # Use small delay for testing
        assert response.status_code == 200
        data = response.json()
        assert "delay" in data
        assert data["delay"] == 0.1
    
    def test_slow_endpoint_message(self, client):
        """Test that slow endpoint returns expected message."""
        response = client.get("/products/slow/0.1")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "0.1" in data["message"]


class TestErrorEndpoint:
    """Tests for the controlled error endpoint."""
    
    def test_error_endpoint_returns_500(self, client):
        """Test that error endpoint returns 500 status."""
        response = client.get("/products/error")
        assert response.status_code == 500
        data = response.json()
        assert "Controlled internal server error" in data["detail"]


class TestCorrelationId:
    """Tests for correlation ID (trace-id) propagation."""
    
    def test_trace_id_propagation(self, client):
        """Test that provided X-Trace-ID is propagated in response."""
        trace_id = "test-trace-id-67890"
        response = client.get("/products", headers={"X-Trace-ID": trace_id})
        assert response.status_code == 200
        assert response.headers.get("X-Trace-ID") == trace_id
    
    def test_trace_id_generated_when_not_provided(self, client):
        """Test that X-Trace-ID is generated when not provided."""
        response = client.get("/products")
        assert response.status_code == 200
        assert "X-Trace-ID" in response.headers
        # Verify it's a valid UUID format
        trace_id = response.headers.get("X-Trace-ID")
        assert len(trace_id) == 36  # UUID format
