from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str


@app.get("/items")
def list_items():
    return []


@app.post("/items")
def create_item(item: Item):
    return item
