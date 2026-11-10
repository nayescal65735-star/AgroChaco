from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.database import router as database_router
from app.api.simulations import router as simulations_router

app = FastAPI(
    title="AgroChaco API",
    description="API del simulador paralelo y distribuido de estrés hídrico en cultivos de maíz.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(simulations_router)
