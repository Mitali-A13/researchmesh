from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.database import engine
from backend.db.models import Base
from backend.routes.auth import router as auth_router
from backend.routes.history import router as history_router
from backend.routes.research import router as research_router

# create DB tables
Base.metadata.create_all(bind=engine)

# app config
app = FastAPI(
    title="AI Research Assistant API",
    version="1.0.0",
    description="API for generating AI-powered research reports using multi-agent pipeline.",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://think-mesh-ai.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/")
def home():
    return {"success": True, "message": "API is running"}


app.include_router(auth_router)
app.include_router(research_router)
app.include_router(history_router)
