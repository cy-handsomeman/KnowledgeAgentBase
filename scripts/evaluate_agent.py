"""Run the fixed Agent task set against an explicitly isolated local eval database."""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "app"))

EVAL_DATABASE_URL = os.environ.get("AGENT_EVAL_DATABASE_URL", "")
if not EVAL_DATABASE_URL:
    raise SystemExit("Set AGENT_EVAL_DATABASE_URL to a dedicated local MySQL database ending in _eval")

from sqlalchemy.engine import make_url  # noqa: E402

eval_url = make_url(EVAL_DATABASE_URL)
if (
    eval_url.drivername != "mysql+pymysql"
    or not eval_url.database
    or not eval_url.database.endswith("_eval")
    or eval_url.host not in {"127.0.0.1", "localhost", "::1"}
    or not eval_url.username
):
    raise SystemExit("Refusing to run: evaluation URL must be local MySQL with a named database ending in _eval")

os.environ["DATABASE_URL"] = EVAL_DATABASE_URL
os.environ["CHROMA_DIR"] = str(ROOT / "storage" / "chroma_agent_eval")
os.environ["UPLOAD_DIR"] = str(ROOT / "storage" / "uploads_agent_eval")

from sqlalchemy import create_engine  # noqa: E402

import models  # noqa: E402,F401
from core.settings import settings  # noqa: E402
from db.base import Base  # noqa: E402
from db.session import SessionLocal  # noqa: E402
from evaluate_rag import (  # noqa: E402
    QUESTIONS,
    cleanup_eval_scope,
    reset_eval_scope,
    seed_documents,
)
from services.agent import MAX_TOOL_CALLS, TOOL_NAME, run_agent  # noqa: E402
from services.llm import LLMError  # noqa: E402


def evaluate_one(db, user, knowledge_base, item):
    started = time.perf_counter()
    record = {
        "question": item["question"],
        "type": item["type"],
        "answerable": item["type"] != "unanswerable",
    }
    try:
        (
            _, answer, sources, has_evidence, steps, model_calls,
            elapsed_seconds, tool_limit_reached, _,
        ) = run_agent(db, user.id, knowledge_base.id, item["question"], None)
        expected = item.get("expect") or []
        answer_hit = any(term in answer for term in expected) if expected else None
        record.update({
            "has_evidence": has_evidence,
            "answer_keyword_hit": answer_hit,
            "citation_valid": bool(sources) if has_evidence else not sources,
            "tool_names": [step.tool for step in steps],
            "tool_call_count": len(steps),
            "model_call_count": model_calls,
            "max_tool_limit_reached": tool_limit_reached,
            "elapsed_seconds": elapsed_seconds,
            "answer": answer,
        })
        record["tool_selection_valid"] = TOOL_NAME in record["tool_names"]
        record["task_completed"] = (
            (has_evidence and answer_hit is not False)
            if item["type"] != "unanswerable"
            else not has_evidence
        )
    except Exception as error:  # include task failures in the report
        record.update({
            "error_type": type(error).__name__,
            "error": "任务执行失败，详细异常仅保留在本地运行日志中。",
            "timed_out": isinstance(error, LLMError) and "时限" in str(error),
            "task_completed": False,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        })
    return record


def summarize(rows, permission_denied):
    completed = sum(bool(row.get("task_completed")) for row in rows)
    tools = [row.get("tool_call_count", 0) for row in rows]
    total_model_calls = sum(row.get("model_call_count", 0) for row in rows)
    times = [row["elapsed_seconds"] for row in rows if "elapsed_seconds" in row]
    citation_rows = [row for row in rows if row.get("has_evidence")]
    valid_citations = sum(bool(row.get("citation_valid")) for row in citation_rows)
    return {
        "task_count": len(rows),
        "task_completion_rate": round(completed / len(rows), 3) if rows else 0,
        "tool_selection_valid_rate": round(
            sum(bool(row.get("tool_selection_valid")) for row in rows) / len(rows), 3
        ) if rows else 0,
        "average_tool_calls": round(sum(tools) / len(tools), 3) if tools else 0,
        "max_tool_limit_reached_count": sum(
            bool(row.get("max_tool_limit_reached")) for row in rows
        ),
        "unanswerable_correct_refusal_rate": round(
            sum(row.get("type") == "unanswerable" and not row.get("has_evidence") for row in rows)
            / max(1, sum(row.get("type") == "unanswerable" for row in rows)), 3
        ),
        "citation_valid_rate_when_answered": round(
            valid_citations / len(citation_rows), 3
        ) if citation_rows else None,
        "unauthorized_access_denied": permission_denied,
        "average_elapsed_seconds": round(sum(times) / len(times), 3) if times else 0,
        "timeouts": sum(bool(row.get("timed_out")) for row in rows),
        "model_call_count": total_model_calls,
        "model_cost": None,
        "model_cost_note": "未接入供应商账单数据，无法可靠统计费用。",
    }


def main():
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    # Create missing schema only in the explicitly guarded _eval database.
    Base.metadata.create_all(engine)
    db = SessionLocal()
    rows = []
    permission_denied = False
    try:
        user, knowledge_base = reset_eval_scope(db)
        seed_documents(db, user, knowledge_base)
        for item in QUESTIONS:
            rows.append(evaluate_one(db, user, knowledge_base, item))
        try:
            run_agent(db, user.id + 10**9, knowledge_base.id, "权限探测", None)
        except PermissionError:
            permission_denied = True
    finally:
        try:
            cleanup_eval_scope(db)
        finally:
            db.close()
            engine.dispose()

    summary = summarize(rows, permission_denied)
    report = {
        "dataset_id": "rag_questions_v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "model": settings.llm_model,
        "max_tool_calls": MAX_TOOL_CALLS,
        "question_count": len(QUESTIONS),
        "summary": summary,
        "rows": rows,
    }
    output_dir = ROOT / "storage" / "eval"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"agent_eval_{datetime.now():%Y%m%d_%H%M%S}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report: {output_path}")


if __name__ == "__main__":
    main()
