import os
import time
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, Request, Response
from loguru import logger
from dotenv import load_dotenv
from typing import List
import httpx  # Pour appels HTTP
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from models import Order, orders_db
from schemas import OrderCreate, OrderResponse

# Chargement des variables d'environnement
load_dotenv()

SERVICE_NAME = "orders-service"

# URLs des services (de local à Docker)
USERS_URL = os.getenv("USERS_SERVICE_URL", "http://localhost:8000")
PRODUCTS_URL = os.getenv("PRODUCTS_SERVICE_URL", "http://localhost:8001")

# Config logging JSON
logger.remove()
logger.add(
    sink="logs.json",
    format="{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level} | {message} | {extra}",
    level="INFO",
    serialize=True,
    rotation="1 day",
)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "endpoint"]
)
ERROR_COUNT = Counter(
    "http_errors_total",
    "Total HTTP errors",
    ["service", "endpoint", "error_type"]
)
EXTERNAL_CALL_COUNT = Counter(
    "external_service_calls_total",
    "Total external service calls",
    ["service", "target_service", "status"]
)
EXTERNAL_CALL_LATENCY = Histogram(
    "external_service_call_duration_seconds",
    "External service call latency in seconds",
    ["service", "target_service"]
)

app = FastAPI(title="Orders Service")


# Middleware pour logger les requests avec correlation ID
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Generate or propagate correlation ID (trace-id)
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    start_time = time.time()
    
    # Store trace_id in request state for use in other handlers
    request.state.trace_id = trace_id
    
    # Bind trace_id to logger context
    with logger.contextualize(trace_id=trace_id, service=SERVICE_NAME):
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={"method": request.method, "url": str(request.url), "trace_id": trace_id}
        )
        
        response = await call_next(request)
        
        # Calculate latency
        latency = time.time() - start_time
        
        # Record metrics
        REQUEST_COUNT.labels(
            service=SERVICE_NAME,
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        REQUEST_LATENCY.labels(
            service=SERVICE_NAME,
            method=request.method,
            endpoint=request.url.path
        ).observe(latency)
        
        logger.info(
            f"Response status: {response.status_code}",
            extra={"status": response.status_code, "latency": latency, "trace_id": trace_id}
        )
        
        # Add trace_id to response headers for tracing
        response.headers["X-Trace-ID"] = trace_id
        return response


@app.get("/metrics")
async def metrics():
    """Endpoint /metrics compatible Prometheus"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": SERVICE_NAME}


async def validate_user(user_id: int, trace_id: str = None):
    """Valide l'existence de l'utilisateur via Users Service"""
    start_time = time.time()
    headers = {"X-Trace-ID": trace_id} if trace_id else {}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{USERS_URL}/users/{user_id}", headers=headers)
            latency = time.time() - start_time
            
            EXTERNAL_CALL_COUNT.labels(
                service=SERVICE_NAME,
                target_service="users-service",
                status="success" if resp.status_code == 200 else "error"
            ).inc()
            EXTERNAL_CALL_LATENCY.labels(
                service=SERVICE_NAME,
                target_service="users-service"
            ).observe(latency)
            
            if resp.status_code != 200:
                logger.warning(f"User {user_id} validation failed", extra={"trace_id": trace_id})
                ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/orders/create", error_type="user_not_found").inc()
                raise HTTPException(status_code=404, detail="User not found")
            logger.info(f"User {user_id} validated", extra={"trace_id": trace_id})
        except httpx.RequestError as e:
            logger.error(f"Error calling users service: {str(e)}", extra={"trace_id": trace_id})
            EXTERNAL_CALL_COUNT.labels(
                service=SERVICE_NAME,
                target_service="users-service",
                status="error"
            ).inc()
            raise HTTPException(status_code=503, detail="Users service unavailable")


async def validate_product(product_id: int, trace_id: str = None):
    """Valide l'existence du produit via Products Service"""
    start_time = time.time()
    headers = {"X-Trace-ID": trace_id} if trace_id else {}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{PRODUCTS_URL}/products/{product_id}", headers=headers)
            latency = time.time() - start_time
            
            EXTERNAL_CALL_COUNT.labels(
                service=SERVICE_NAME,
                target_service="products-service",
                status="success" if resp.status_code == 200 else "error"
            ).inc()
            EXTERNAL_CALL_LATENCY.labels(
                service=SERVICE_NAME,
                target_service="products-service"
            ).observe(latency)
            
            if resp.status_code != 200:
                logger.warning(f"Product {product_id} validation failed", extra={"trace_id": trace_id})
                ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/orders/create", error_type="product_not_found").inc()
                raise HTTPException(status_code=404, detail="Product not found")
            logger.info(f"Product {product_id} validated", extra={"trace_id": trace_id})
        except httpx.RequestError as e:
            logger.error(f"Error calling products service: {str(e)}", extra={"trace_id": trace_id})
            EXTERNAL_CALL_COUNT.labels(
                service=SERVICE_NAME,
                target_service="products-service",
                status="error"
            ).inc()
            raise HTTPException(status_code=503, detail="Products service unavailable")


@app.get("/orders", response_model=List[OrderResponse])
async def get_orders():
    logger.info("Fetching all orders")
    return orders_db


# Scénario de dysfonctionnement: Service lent simulé (must be before {order_id} route)
@app.get("/orders/slow/{delay_seconds}")
async def slow_endpoint(delay_seconds: float = 2.0):
    """
    Endpoint simulant une latence artificielle.
    Utilisé pour tester l'observabilité des services lents.
    """
    logger.warning(f"Slow endpoint called with delay: {delay_seconds}s")
    await asyncio.sleep(delay_seconds)
    logger.info(f"Slow endpoint completed after {delay_seconds}s")
    return {"message": f"Response after {delay_seconds} seconds delay", "delay": delay_seconds}


# Scénario de dysfonctionnement: Service en erreur contrôlée (must be before {order_id} route)
@app.get("/orders/error")
async def error_endpoint():
    """
    Endpoint générant volontairement une erreur HTTP 500.
    Utilisé pour tester la propagation des erreurs et l'observabilité.
    """
    logger.error("Controlled error triggered", extra={"error_type": "controlled_500"})
    ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/orders/error", error_type="controlled_500").inc()
    raise HTTPException(status_code=500, detail="Controlled internal server error for testing")


# Scénario: Propagation d'erreur depuis un service dépendant (must be before {order_id} route)
@app.get("/orders/cascade-error")
async def cascade_error_endpoint(request: Request):
    """
    Endpoint testant la propagation d'erreur à travers les services.
    Appelle le service users avec un endpoint d'erreur pour observer la cascade.
    """
    trace_id = getattr(request.state, 'trace_id', str(uuid.uuid4()))
    logger.info("Testing cascade error propagation", extra={"trace_id": trace_id})
    
    headers = {"X-Trace-ID": trace_id}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{USERS_URL}/users/error", headers=headers)
            logger.error(f"Cascade error received from users service: {resp.status_code}", extra={"trace_id": trace_id})
            ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/orders/cascade-error", error_type="cascade_error").inc()
            raise HTTPException(status_code=500, detail=f"Cascade error from users service: {resp.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Error during cascade test: {str(e)}", extra={"trace_id": trace_id})
            raise HTTPException(status_code=503, detail="Users service unavailable during cascade test")


@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int):
    logger.info(f"Fetching order {order_id}")
    order = next((o for o in orders_db if o.id == order_id), None)
    if not order:
        logger.warning(f"Order {order_id} not found")
        ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/orders/{order_id}", error_type="not_found").inc()
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/orders/create", response_model=OrderResponse)
async def create_order(order: OrderCreate, request: Request):
    trace_id = getattr(request.state, 'trace_id', str(uuid.uuid4()))
    logger.info(f"Creating order for user {order.user_id}, product {order.product_id}", extra={"trace_id": trace_id})
    
    # Validation inter-services avec propagation du trace_id
    await validate_user(order.user_id, trace_id)
    await validate_product(order.product_id, trace_id)
    
    new_id = max(o.id for o in orders_db) + 1 if orders_db else 1
    new_order = Order(id=new_id, user_id=order.user_id, product_id=order.product_id, quantity=order.quantity)
    orders_db.append(new_order)
    logger.info(f"Order created with ID {new_id}", extra={"trace_id": trace_id})
    return new_order


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8002))
    logger.info(f"Starting Orders Service on port {port}")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)