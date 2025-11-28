import os
import time
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, Request, Response
from loguru import logger
from dotenv import load_dotenv
from typing import List
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from models import User, users_db
from schemas import UserCreate, UserResponse

# Chargement des variables d'environnement
load_dotenv()

SERVICE_NAME = "users-service"

# Config logging JSON (niveaux INFO, WARNING, ERROR)
logger.remove()  # Supprime le handler par défaut
logger.add(
    sink="logs.json",
    format="{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level} | {message} | {extra}",
    level="INFO",
    serialize=True,  # Format JSON
    rotation="1 day",  # Rotation quotidienne
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

app = FastAPI(title="Users Service")


# Middleware pour logger les requests avec correlation ID (observabilité)
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


@app.get("/users", response_model=List[UserResponse])
async def get_users():
    logger.info("Fetching all users")
    return users_db


# Scénario de dysfonctionnement: Service lent simulé (must be before {user_id} route)
@app.get("/users/slow/{delay_seconds}")
async def slow_endpoint(delay_seconds: float = 2.0):
    """
    Endpoint simulant une latence artificielle.
    Utilisé pour tester l'observabilité des services lents.
    """
    logger.warning(f"Slow endpoint called with delay: {delay_seconds}s")
    await asyncio.sleep(delay_seconds)
    logger.info(f"Slow endpoint completed after {delay_seconds}s")
    return {"message": f"Response after {delay_seconds} seconds delay", "delay": delay_seconds}


# Scénario de dysfonctionnement: Service en erreur contrôlée (must be before {user_id} route)
@app.get("/users/error")
async def error_endpoint():
    """
    Endpoint générant volontairement une erreur HTTP 500.
    Utilisé pour tester la propagation des erreurs et l'observabilité.
    """
    logger.error("Controlled error triggered", extra={"error_type": "controlled_500"})
    ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/users/error", error_type="controlled_500").inc()
    raise HTTPException(status_code=500, detail="Controlled internal server error for testing")


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    logger.info(f"Fetching user {user_id}")
    user = next((u for u in users_db if u.id == user_id), None)
    if not user:
        logger.warning(f"User {user_id} not found")
        ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/users/{user_id}", error_type="not_found").inc()
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/users/create", response_model=UserResponse)
async def create_user(user: UserCreate):
    logger.info(f"Creating user: {user.name}")
    if any(u.email == user.email for u in users_db):
        logger.error(f"Email {user.email} already exists")
        ERROR_COUNT.labels(service=SERVICE_NAME, endpoint="/users/create", error_type="duplicate_email").inc()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_id = max(u.id for u in users_db) + 1 if users_db else 1
    new_user = User(id=new_id, name=user.name, email=user.email)
    users_db.append(new_user)
    logger.info(f"User created with ID {new_id}")
    return new_user


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting Users Service on port {port}")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)