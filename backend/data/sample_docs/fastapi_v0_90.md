# FastAPI Documentation (Version 0.90.0)

## Overview
FastAPI is a modern, fast web framework for building APIs with Python 3.7+ based on standard Python type hints and Pydantic v1.

## Application Lifecycle & Startup Events
In FastAPI 0.90, application startup and shutdown events are handled using `@app.on_event`:

```python
from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    print("Connecting to database...")

@app.on_event("shutdown")
async def shutdown_event():
    print("Disconnecting from database...")
```

## Request Models & Validation (Pydantic v1)
Define request bodies using Pydantic `BaseModel`. In FastAPI 0.90, models use Pydantic v1 syntax:

```python
from pydantic import BaseModel, validator

class Item(BaseModel):
    name: str
    price: float
    is_offer: bool = None

    @validator("price")
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Price must be positive")
        return v

@app.post("/items/")
def create_item(item: Item):
    item_dict = item.dict()
    return item_dict
```

## Dependency Injection
Use `Depends` to inject database sessions and security handlers:

```python
from fastapi import Depends

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/users/")
def read_users(db = Depends(get_db)):
    return db.query(User).all()
```
