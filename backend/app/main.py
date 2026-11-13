from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from api.auth import router as auth_router
from api.agent import router as agent_router
from api.ask import router as ask_router
from api.chat import router as chat_router
from api.documents import router as documents_router
from api.groups import router as groups_router
from api.knowledge_bases import router as knowledge_bases_router
from api.search import router as search_router
from api.users import router as users_router
from core.settings import settings
from db.session import engine

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="企业文档知识库")
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(groups_router)
app.include_router(knowledge_bases_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(ask_router)
app.include_router(chat_router)
app.include_router(users_router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "database_url_configured": bool(settings.database_url),
        "llm_model": settings.llm_model,
    }


@app.get("/api/health/db")
def health_db():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
