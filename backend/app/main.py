from fastapi import FastAPI

from app.api.database import router as database_router

app = FastAPI(
    title="AgroChaco API",
    description="API del simulador paralelo y distribuido de estrés hídrico en cultivos de maíz.",
    version="1.0.0",
)


@app.get("/")
def inicio():
    return {
        "proyecto": "AgroChaco",
        "mensaje": "Backend funcionando correctamente",
        "version": "1.0.0",
    }


@app.get("/api/health")
def health():
    return {
        "estado": "activo",
        "servicio": "AgroChaco API",
    }


app.include_router(database_router)
