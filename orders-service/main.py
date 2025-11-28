import os
from fastapi import FastAPI, HTTPException, Depends
from loguru import logger
from dotenv import load_dotenv
from typing import List
import httpx  # Pour appels HTTP
from models import Order, orders_db
from schemas import OrderCreate, OrderResponse

# Chargement des variables d'environnement
load_dotenv()

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

app = FastAPI(title="Orders Service")

# Middleware pour logger les requests
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Request: {request.method} {request.url}", extra={"method": request.method, "url": str(request.url)})
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}", extra={"status": response.status_code})
    return response

async def validate_user(user_id: int):
    """Valide l'existence de l'utilisateur via Users Service"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{USERS_URL}/users/{user_id}")
        if resp.status_code != 200:
            logger.warning(f"User {user_id} validation failed")
            raise HTTPException(status_code=404, detail="User not found")
        logger.info(f"User {user_id} validated")

async def validate_product(product_id: int):
    """Valide l'existence du produit via Products Service"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PRODUCTS_URL}/products/{product_id}")
        if resp.status_code != 200:
            logger.warning(f"Product {product_id} validation failed")
            raise HTTPException(status_code=404, detail="Product not found")
        logger.info(f"Product {product_id} validated")

@app.get("/orders", response_model=List[OrderResponse])
async def get_orders():
    logger.info("Fetching all orders")
    return orders_db

@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int):
    logger.info(f"Fetching order {order_id}")
    order = next((o for o in orders_db if o.id == order_id), None)
    if not order:
        logger.warning(f"Order {order_id} not found")
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.post("/orders/create", response_model=OrderResponse)
async def create_order(order: OrderCreate):
    logger.info(f"Creating order for user {order.user_id}, product {order.product_id}")
    
    # Validation inter-services (ajoute headers si besoin pour auth)
    await validate_user(order.user_id)
    await validate_product(order.product_id)
    
    new_id = max(o.id for o in orders_db) + 1 if orders_db else 1
    new_order = Order(id=new_id, user_id=order.user_id, product_id=order.product_id, quantity=order.quantity)
    orders_db.append(new_order)
    logger.info(f"Order created with ID {new_id}")
    return new_order

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8002))
    logger.info(f"Starting Orders Service on port {port}")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)