import os
from fastapi import FastAPI, HTTPException
from loguru import logger
from dotenv import load_dotenv
from typing import List
from models import User, users_db
from schemas import UserCreate, UserResponse

# Chargement des variables d'environnement
load_dotenv()

# Config logging JSON (niveaux INFO, WARNING, ERROR)
logger.remove()  # Supprime le handler par défaut
logger.add(
    sink="logs.json",
    format="{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level} | {message} | {extra}",
    level="INFO",
    serialize=True,  # Format JSON
    rotation="1 day",  # Rotation quotidienne
)

app = FastAPI(title="Users Service")

# Middleware pour logger les requests (observabilité)
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Request: {request.method} {request.url}", extra={"method": request.method, "url": str(request.url)})
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}", extra={"status": response.status_code})
    return response

@app.get("/users", response_model=List[UserResponse])
async def get_users():
    logger.info("Fetching all users")
    return users_db

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    logger.info(f"Fetching user {user_id}")
    user = next((u for u in users_db if u.id == user_id), None)
    if not user:
        logger.warning(f"User {user_id} not found")
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/users/create", response_model=UserResponse)
async def create_user(user: UserCreate):
    logger.info(f"Creating user: {user.name}")
    if any(u.email == user.email for u in users_db):
        logger.error(f"Email {user.email} already exists")
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