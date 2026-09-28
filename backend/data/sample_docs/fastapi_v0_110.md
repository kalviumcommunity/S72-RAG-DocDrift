# FastAPI Documentation (Version 0.110.0)

## Overview
FastAPI 0.110.0 features full compatibility with Pydantic v2, Python 3.10+ `Annotated` typing, and asynchronous Lifespan context managers for application lifecycle management.

## Lifespan Events (Replaces on_event)
The `@app.on_event("startup")` and `@app.on_event("shutdown")` decorators are deprecated. Modern FastAPI applications use the `lifespan` parameter with `@asynccontextmanager`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Database connection pool initialized.")
    yield
    # Shutdown logic
    print("Database connection pool closed.")

app = FastAPI(lifespan=lifespan)
```

## Request Models & Validation (Pydantic v2)
FastAPI 0.110 uses Pydantic v2. Key method migrations:
- Replace `item.dict()` with `item.model_dump()`.
- Replace `item.json()` with `item.model_dump_json()`.
- Replace `@validator` with `@field_validator(mode="after")`.
- Replace `@root_validator` with `@model_validator(mode="after")`.

```python
from pydantic import BaseModel, field_validator

class Item(BaseModel):
    name: str
    price: float
    is_offer: bool | None = None

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Price must be positive")
        return v

@app.post("/items/")
async def create_item(item: Item):
    return item.model_dump()
```

## Dependency Injection with Annotated
Use `typing.Annotated` for cleaner dependency definitions:

```python
from typing import Annotated
from fastapi import Depends

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DbSession = Annotated[Session, Depends(get_db)]

@app.get("/users/")
async def read_users(db: DbSession):
    return await db.execute(select(User))
```
