from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import router as auth_router
from src.api.health import router as health_router
from src.config import settings

app = FastAPI(
    title="Retail Order Tracker API",
    description=(
        "AI-augmented EDI operations platform with human-in-the-loop review. "
        "Parses retailer purchase orders in JSON / XML / CSV / EDIFACT / PDF, "
        "runs an Analyst Agent to suggest an action, and exposes a review queue."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
