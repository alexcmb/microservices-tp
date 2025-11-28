from typing import List
from pydantic import BaseModel

class Product(BaseModel):
    id: int
    name: str
    price: float

# Stockage en mémoire (exemple)
products_db: List[Product] = [
    Product(id=1, name="Laptop", price=999.99),
    Product(id=2, name="Souris", price=29.99),
]