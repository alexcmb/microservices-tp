from pydantic import BaseModel, validator

class OrderCreate(BaseModel):
    user_id: int
    product_id: int
    quantity: int

    @validator('quantity')
    def quantity_must_be_positive(cls, v):
        if v < 1:
            raise ValueError('Quantity must be positive')
        return v

class OrderResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    quantity: int

    class Config:
        from_attributes = True