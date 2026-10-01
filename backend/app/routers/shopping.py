"""Shopping list and errands CRUD."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.reminder import ShoppingItem, Errand
from app.config import settings as app_settings

router = APIRouter(prefix="/shopping", tags=["shopping"])


class ShoppingItemIn(BaseModel):
    item: str
    store: str = ""
    quantity: str = ""
    category: str = ""


class ErrandIn(BaseModel):
    text: str
    place: str | None = None
    due_hint: str | None = None


# ─── Shopping List ────────────────────────────────────────────────────────────

@router.get("/")
def get_shopping_list(store: str = "", db: Session = Depends(get_db)):
    q = db.query(ShoppingItem).filter_by(user_id=app_settings.friday_user_id, checked=False)
    if store:
        q = q.filter(ShoppingItem.store.ilike(f"%{store}%"))
    items = q.order_by(ShoppingItem.store, ShoppingItem.item).all()
    return [{"id": i.id, "item": i.item, "store": i.store, "quantity": i.quantity,
             "checked": i.checked} for i in items]


@router.post("/", status_code=201)
def add_item(body: ShoppingItemIn, db: Session = Depends(get_db)):
    item = ShoppingItem(
        id=str(uuid.uuid4()), user_id=app_settings.friday_user_id,
        item=body.item, store=body.store, quantity=body.quantity, category=body.category,
    )
    db.add(item)
    db.commit()
    return {"id": item.id, "item": item.item}


@router.put("/{item_id}/check")
def check_item(item_id: str, db: Session = Depends(get_db)):
    item = db.get(ShoppingItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    item.checked = True
    db.commit()
    return {"id": item_id, "checked": True}


@router.delete("/{item_id}")
def delete_item(item_id: str, db: Session = Depends(get_db)):
    item = db.get(ShoppingItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()
    return {"deleted": item_id}


@router.delete("/clear-checked")
def clear_checked(db: Session = Depends(get_db)):
    count = db.query(ShoppingItem).filter_by(user_id=app_settings.friday_user_id, checked=True).count()
    db.query(ShoppingItem).filter_by(user_id=app_settings.friday_user_id, checked=True).delete()
    db.commit()
    return {"cleared": count}


# ─── Errands ─────────────────────────────────────────────────────────────────

errands_router = APIRouter(prefix="/errands", tags=["errands"])


@errands_router.get("/")
def get_errands(db: Session = Depends(get_db)):
    rows = db.query(Errand).filter_by(user_id=app_settings.friday_user_id, status="pending").all()
    return [{"id": r.id, "text": r.text, "place": r.place, "due_hint": r.due_hint} for r in rows]


@errands_router.post("/", status_code=201)
def add_errand(body: ErrandIn, db: Session = Depends(get_db)):
    e = Errand(
        id=str(uuid.uuid4()), user_id=app_settings.friday_user_id,
        text=body.text, place=body.place, due_hint=body.due_hint,
    )
    db.add(e)
    db.commit()
    return {"id": e.id, "text": e.text}


@errands_router.put("/{errand_id}/done")
def complete_errand(errand_id: str, db: Session = Depends(get_db)):
    e = db.get(Errand, errand_id)
    if not e:
        raise HTTPException(404, "Errand not found")
    e.status = "done"
    db.commit()
    return {"id": errand_id, "status": "done"}
