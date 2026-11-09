from fastapi import FastAPI
from sqlalchemy import text

from core.settings import settings
from db.session import engine
from schemas.question import QuestionRequest

app = FastAPI(title="企业文档知识库")


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


@app.post("/api/questions/validate")
def validate_question(payload: QuestionRequest):
    return {"received": payload.model_dump()}
