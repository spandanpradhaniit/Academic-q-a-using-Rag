from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.connection import get_db
router=APIRouter(tags=["health"])
@router.get("/health",summary="Check API and database availability")
def health(db:Session=Depends(get_db)):
    try: db.execute(text("SELECT 1")); return {"status":"healthy","database":"connected"}
    except Exception: return {"status":"degraded","database":"unavailable"}
