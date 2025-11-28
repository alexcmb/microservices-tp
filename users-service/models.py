from typing import List
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
    email: str

# Stockage en mémoire (exemple)
users_db: List[User] = [
    User(id=1, name="Alice", email="alice@example.com"),
    User(id=2, name="Bob", email="bob@example.com"),
]