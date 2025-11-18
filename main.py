import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product, Order, OrderItem, User

app = FastAPI(title="E-commerce API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductResponse(Product):
    id: str

class OrderResponse(BaseModel):
    id: str


@app.get("/")
def read_root():
    return {"message": "E-commerce API running"}


@app.get("/schema")
def get_schema_info():
    # Expose available schema names for tooling/validation UIs
    return {
        "collections": ["user", "product", "order"],
        "notes": "Models are defined in schemas.py"
    }


@app.get("/products", response_model=List[ProductResponse])
def list_products(category: Optional[str] = None, q: Optional[str] = None, limit: int = 50):
    if db is None:
        return []
    filt = {}
    if category:
        filt["category"] = category
    if q:
        filt["title"] = {"$regex": q, "$options": "i"}
    docs = get_documents("product", filt, limit)
    results = []
    for d in docs:
        d["id"] = str(d.get("_id"))
        d.pop("_id", None)
        results.append(d)
    return results


@app.post("/products", response_model=str)
def create_product(product: Product):
    try:
        new_id = create_document("product", product)
        return new_id
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Product not found")
        doc["id"] = str(doc["_id"]) ; doc.pop("_id", None)
        return doc
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID")


@app.post("/orders", response_model=str)
def create_order(order: Order):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    # Compute total server-side
    total = 0.0
    for item in order.items:
        prod = db["product"].find_one({"_id": ObjectId(item.product_id)})
        if not prod:
            raise HTTPException(status_code=404, detail=f"Product not found: {item.product_id}")
        total += float(prod.get("price", 0)) * item.quantity

    payload = order.model_dump()
    payload["total"] = round(total, 2)
    try:
        new_id = create_document("order", payload)
        return new_id
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
