from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db

router = APIRouter(prefix="/api/database", tags=["Database"])


@router.get("/test")
def test_database(db: Session = Depends(get_db)):
    try:
        result = db.execute(
            text("SELECT current_database(), current_user, version()")
        ).fetchone()

        return {
            "estado": "conectado",
            "base_datos": result[0],
            "usuario": result[1],
            "version": result[2],
        }

    except Exception as error:
        return {
            "estado": "error",
            "mensaje": str(error),
        }
