from pydantic import BaseModel, constr  # constr pour valider name (string non vide)

class ProductCreate(BaseModel):
    name: constr(min_length=1)  # Nom obligatoire et non vide
    price: float  # En prod, ajoute >0 avec validator

class ProductResponse(BaseModel):
    id: int
    name: str
    price: float

    class Config:
        from_attributes = True