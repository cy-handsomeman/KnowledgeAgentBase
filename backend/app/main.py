from fastapi import FastAPI

from schemas.question import QuestionRequest

app = FastAPI(title="企业文档知识库")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/questions/validate")
def validate_question(payload: QuestionRequest):
    return {"received": payload.model_dump()}
