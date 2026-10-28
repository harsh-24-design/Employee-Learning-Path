from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.routes import router
from app.services.ingestion import DataIngestionService
from app.repositories.mongo_repository import repository

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure initial ingestion from data/ directory on startup
    courses = repository.get_all_courses()
    if not courses:
        print("Data repository uninitialized. Executing automatic initial ingestion...")
        res = DataIngestionService.ingest_all()
        print(f"Ingestion finished: {res['total_records']} records imported.")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Employee Learning Path Advisory Agent REST API",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {
        "message": "Employee Learning Path Advisory Agent API is active.",
        "documentation": "/docs",
        "health": f"{settings.API_V1_STR}/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
