from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.seed_service import seed_initial_data
from app.api.v1.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed database with initial hotel demo records only in non-production environments
    if settings.ENVIRONMENT.lower() != "production" and settings.ENABLE_DEMO_SEEDING:
        async with AsyncSessionLocal() as session:
            try:
                await seed_initial_data(session)
            except Exception as e:
                print(f"[Startup Seed Error] {e}")
    else:
        print(f"[Startup] Demo seeding disabled for ENVIRONMENT={settings.ENVIRONMENT}")
    yield
    # Shutdown logic if any

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-Ready Multi-Tenant Hotel Management SaaS API",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "timezone": settings.DEFAULT_TIMEZONE,
        "currency": settings.DEFAULT_CURRENCY
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

