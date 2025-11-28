from typing import List
from pydantic import BaseModel

class Order(BaseModel):
    id: int
    user_id: int
    product_id: int
    quantity: int

# Stockage en mémoire (exemple)
orders_db: List[Order] = [
    Order(id=1, user_id=1, product_id=1, quantity=2),
    Order(id=2, user_id=2, product_id=2, quantity=1),
]