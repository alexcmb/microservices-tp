import os
import time
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, Request, Response
from loguru import logger
from dotenv import load_dotenv
from typing import List
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from models import Product, products_db
from schemas import ProductCreate, ProductResponse

# Chargement des variables d'environnement
load_dotenv()

SERVICE_NAME = "products-service"

# Config logging JSON (niveaux INFO, WARNING, ERROR)
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

app = FastAPI(title="Products Service")


# Middleware pour logger les requests avec correlation ID
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Generate or propagate correlation ID (trace-id)
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    start_time = time.time()
    
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


@app.get("/products", response_model=List[ProductResponse])
async def get_products():
    logger.info("Fetching all products")
    return products_db


# Scénario de dysfonctionnement: Service lent simulé (must be before {product_id} route)
@app.get("/products/slow/{delay_seconds}")
async def slow_endpoint(delay_seconds: float = 2.0):
    """
    Endpoint simulant une latence artificielle.
    Utilisé pour tester l'observabilité des services lents.
    """
    logger.warning(f"Slow endpoint called with delay: {delay_seconds}s")
    await asyncio.sleep(delay_seconds)
    logger.info(f"Slow endpoint completed after {delay_seconds}s")
    return {"message": f"Response after {delay_seconds} seconds delay", "delay": delay_seconds}


# Scénario de dysfonctionnement: Service en erreur contrôlée (must be before {product_id} route)
@app.get("/products/error")
async def error_endpoint():
    """
    Endpoint générant volontairement une erreur HTTP 500.
    Utilisé pour tester la propagation des erreurs et l'observabilité.
    """
    logger.error("Controlled error triggered", extra={"error_type": "controlled_500"})
    ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/products/error", error_type="controlled_500").inc()
    raise HTTPException(status_code=500, detail="Controlled internal server error for testing")


@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int):
    logger.info(f"Fetching product {product_id}")
    product = next((p for p in products_db if p.id == product_id), None)
    if not product:
        logger.warning(f"Product {product_id} not found")
        ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/products/{product_id}", error_type="not_found").inc()
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.post("/products/create", response_model=ProductResponse)
async def create_product(product: ProductCreate):
    logger.info(f"Creating product: {product.name}")
    if any(p.name.lower() == product.name.lower() for p in products_db):  # Check unicité nom
        logger.error(f"Product name {product.name} already exists")
        ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/products/create", error_type="duplicate_name").inc()
        raise HTTPException(status_code=400, detail="Product name already exists")
    
    new_id = max(p.id for p in products_db) + 1 if products_db else 1
    new_product = Product(id=new_id, name=product.name, price=product.price)
    products_db.append(new_product)
    logger.info(f"Product created with ID {new_id}")
    return new_product


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    logger.info(f"Starting Products Service on port {port}")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)