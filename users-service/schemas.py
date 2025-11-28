from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    name: str
    email: EmailStr  # Valide l'email automatiquement

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True  # Pour compatibilité Pydantic v2