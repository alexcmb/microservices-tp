import os
from fastapi import FastAPI, HTTPException
from loguru import logger
from dotenv import load_dotenv
from typing import List
from models import Product, products_db
from schemas import ProductCreate, ProductResponse

# Chargement des variables d'environnement
load_dotenv()

# Config logging JSON (niveaux INFO, WARNING, ERROR)
logger.remove()
logger.add(
    sink="logs.json",
    format="{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level} | {message} | {extra}",
    level="INFO",
    serialize=True,
    rotation="1 day",
)

app = FastAPI(title="Products Service")

# Middleware pour logger les requests
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Request: {request.method} {request.url}", extra={"method": request.method, "url": str(request.url)})
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}", extra={"status": response.status_code})
    return response

@app.get("/products", response_model=List[ProductResponse])
async def get_products():
    logger.info("Fetching all products")
    return products_db

@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int):
    logger.info(f"Fetching product {product_id}")
    product = next((p for p in products_db if p.id == product_id), None)
    if not product:
        logger.warning(f"Product {product_id} not found")
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.post("/products/create", response_model=ProductResponse)
async def create_product(product: ProductCreate):
    logger.info(f"Creating product: {product.name}")
    if any(p.name.lower() == product.name.lower() for p in products_db):  # Check unicité nom
        logger.error(f"Product name {product.name} already exists")
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