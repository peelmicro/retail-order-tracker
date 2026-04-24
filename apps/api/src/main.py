from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.agents import router as agents_router
from src.api.auth import router as auth_router
from src.api.feedback import router as feedback_router
from src.api.health import router as health_router
from src.api.orders import router as orders_router
from src.api.reports import router as reports_router
from src.api.seed import router as seed_router
from src.api.websockets import router as websockets_router
from src.config import settings
from src.infrastructure.observability.phoenix import init_phoenix


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_phoenix(service_name="retail-order-tracker")
    yield


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
    lifespan=lifespan,
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
app.include_router(agents_router)
app.include_router(orders_router)
app.include_router(feedback_router)
app.include_router(reports_router)
app.include_router(seed_router)
app.include_router(websockets_router)
