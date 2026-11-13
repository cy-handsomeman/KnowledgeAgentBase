"""固定问题集评测：检查严格引用校验在真实模型下的拒答率与引用正确率。

用法（项目根目录）：
    .\\.venv\\Scripts\\python.exe scripts\\evaluate_rag.py

脚本会重建一个独立评测知识库（组名「RAG评测组」），不会影响其它数据。
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "app"))

from sqlalchemy import delete, select  # noqa: E402

from core.security import hash_password  # noqa: E402
from core.settings import settings  # noqa: E402
from db.session import SessionLocal  # noqa: E402
from models.chat import ChatSession  # noqa: E402
from models.document import Document  # noqa: E402
from models.knowledge_base import KnowledgeBase  # noqa: E402
from models.knowledge_group import GroupMember, KnowledgeGroup  # noqa: E402
from models.user import User  # noqa: E402
from services.indexing import index_document  # noqa: E402
from services.llm import LLMError, chat_completion  # noqa: E402
from services.rag import build_messages, parse_answer, parse_model_answer  # noqa: E402
from services.retrieval import retrieve_matches  # noqa: E402
from services.vector_store import delete_document_vectors  # noqa: E402

EVAL_USERNAME = "rag_eval_bot"
EVAL_GROUP_NAME = "RAG评测组"

DOCUMENTS = [
    (
        "差旅管理制度",
        "一线城市出差住宿标准为每晚不超过 600 元，二线城市每晚不超过 400 元。"
        "员工出差需提前 3 个工作日提交出差申请，经直属上级审批后方可出行。"
        "城市间交通优先选择高铁二等座，超过 6 小时车程可选择飞机经济舱。",
    ),
    (
        "年假与休假制度",
        "员工入职满 1 年享受 5 天年假，满 3 年享受 10 天年假，满 10 年享受 15 天年假。"
        "年假需提前 5 个工作日申请。当年未休完的年假可以顺延至次年 3 月 31 日，逾期作废。",
    ),
    (
        "费用报销制度",
        "报销单据需在费用发生后 30 天内提交，逾期需部门负责人书面说明。"
        "发票抬头必须使用公司全称，否则财务不予受理。"
        "单笔报销金额超过 5000 元时，需要部门负责人和财务总监双签。",
    ),
    (
        "信息安全规范",
        "员工账号密码至少 12 位，并且每 90 天必须更换一次。"
        "禁止在个人网盘存放客户数据。发现数据泄露后必须在 1 小时内上报安全组。",
    ),
    (
        "考勤管理办法",
        "标准上班时间为 9:00，允许弹性到 9:30 打卡。"
        "每月迟到累计超过 3 次，扣除当天绩效。"
        "远程办公需提前一天在考勤系统提交申请并获得审批。",
    ),
]

QUESTIONS = [
    {"question": "一线城市出差住宿每晚最多多少钱？", "type": "answerable", "expect": ["600"]},
    {"question": "出差需要提前几个工作日申请？", "type": "answerable", "expect": ["3"]},
    {"question": "入职满 3 年可以享受多少天年假？", "type": "answerable", "expect": ["10"]},
    {"question": "没休完的年假最晚可以延到什么时候？", "type": "answerable", "expect": ["3 月 31", "3月31"]},
    {"question": "报销单据需要在费用发生后多少天内提交？", "type": "answerable", "expect": ["30"]},
    {"question": "单笔报销金额超过多少需要双签？", "type": "answerable", "expect": ["5000", "5,000"]},
    {"question": "发票抬头有什么要求？", "type": "answerable", "expect": ["全称"]},
    {"question": "账号密码多久必须更换一次？", "type": "answerable", "expect": ["90"]},
    {"question": "发现数据泄露后要在多久内上报？", "type": "answerable", "expect": ["1 小时", "1小时", "一小时"]},
    {"question": "每月迟到累计几次以上会扣绩效？", "type": "answerable", "expect": ["3"]},
    {"question": "出差住宿标准分为哪几档？", "type": "partial", "expect": ["一", "二"]},
    {"question": "年假可以跨年使用吗？", "type": "partial", "expect": ["顺延", "3 月 31", "3月31"]},
    {"question": "远程办公要怎么申请？", "type": "partial", "expect": ["提前一天", "考勤系统"]},
    {"question": "出差坐飞机有什么限制？", "type": "partial", "expect": ["经济舱", "6 小时", "6小时"]},
    {"question": "报销需要哪些人签字？", "type": "partial", "expect": ["部门负责人", "财务总监"]},
    {"question": "公司的股票期权怎么分配？", "type": "unanswerable"},
    {"question": "食堂午餐几点开饭？", "type": "unanswerable"},
    {"question": "年终奖是怎么计算的？", "type": "unanswerable"},
    {"question": "员工体检套餐包含哪些项目？", "type": "unanswerable"},
    {"question": "公司一共有几个分公司？", "type": "unanswerable"},
]

CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def _delete_eval_groups(db) -> tuple[int, int]:
    user = db.scalar(select(User).where(User.username == EVAL_USERNAME))
    if user is None:
        return 0, 0
    groups = db.scalars(
        select(KnowledgeGroup).where(
            KnowledgeGroup.name == EVAL_GROUP_NAME,
            KnowledgeGroup.created_by == user.id,
        )
    ).all()
    document_count = 0
    for group in groups:
        knowledge_base = db.scalar(
            select(KnowledgeBase).where(KnowledgeBase.group_id == group.id)
        )
        if knowledge_base is not None:
            for document in db.scalars(
                select(Document).where(
                    Document.knowledge_base_id == knowledge_base.id
                )
            ).all():
                delete_document_vectors(document.id)
                db.delete(document)
                document_count += 1
            db.flush()
            db.delete(knowledge_base)
            db.flush()
        db.execute(delete(GroupMember).where(GroupMember.group_id == group.id))
        db.delete(group)
    db.commit()
    return len(groups), document_count


def cleanup_eval_scope(db) -> dict:
    """删除评测脚本创建的群组、知识库、文档、向量和评测用户。"""
    group_count, document_count = _delete_eval_groups(db)

    user = db.scalar(select(User).where(User.username == EVAL_USERNAME))
    session_count = 0
    if user is not None:
        for session in db.scalars(
            select(ChatSession).where(ChatSession.user_id == user.id)
        ).all():
            db.delete(session)
            session_count += 1
        db.flush()
        db.delete(user)
    db.commit()
    return {
        "groups": group_count,
        "documents": document_count,
        "sessions": session_count,
        "user_deleted": user is not None,
    }


def reset_eval_scope(db):
    user = db.scalar(select(User).where(User.username == EVAL_USERNAME))
    if user is None:
        user = User(username=EVAL_USERNAME, password_hash=hash_password("eval-only"))
        db.add(user)
        db.commit()
        db.refresh(user)

    _delete_eval_groups(db)

    group = KnowledgeGroup(
        name=EVAL_GROUP_NAME, group_type="department", created_by=user.id
    )
    db.add(group)
    db.flush()
    db.add(GroupMember(group_id=group.id, user_id=user.id, role="admin"))
    knowledge_base = KnowledgeBase(
        name=f"{EVAL_GROUP_NAME}知识库",
        scope_type="enterprise_group",
        group_id=group.id,
    )
    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)
    return user, knowledge_base


def seed_documents(db, user, knowledge_base):
    document_ids = []
    for title, content in DOCUMENTS:
        document = Document(
            knowledge_base_id=knowledge_base.id,
            title=title,
            content=content,
            file_type="markdown",
            uploaded_by=user.id,
            status="PROCESSING",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        index_document(db, document)
        db.refresh(document)
        if document.status != "READY":
            raise RuntimeError(f"评测文档索引失败：{title} {document.error_message}")
        document_ids.append(document.id)
    return document_ids


def evaluate_one(db, user, knowledge_base, item):
    started = time.perf_counter()
    matches = retrieve_matches(db, user.id, knowledge_base.id, item["question"])
    expected = item.get("expect") or []
    retrieval_keyword_hit = (
        any(keyword in match.content for keyword in expected for match in matches)
        if expected
        else None
    )
    if not matches:
        return {
            "question": item["question"],
            "type": item["type"],
            "matches": 0,
            "retrieval_expected_keyword_hit": retrieval_keyword_hit,
            "raw_json_ok": None,
            "model_has_evidence": None,
            "citation_numbers": [],
            "invalid_citation": False,
            "final_has_evidence": False,
            "answer": "根据现有资料无法回答。",
            "keyword_hit": None,
            "latency": round(time.perf_counter() - started, 2),
        }

    try:
        raw = chat_completion(
            build_messages(item["question"], matches), json_mode=True
        )
    except LLMError as error:
        return {
            "question": item["question"],
            "type": item["type"],
            "matches": len(matches),
            "retrieval_expected_keyword_hit": retrieval_keyword_hit,
            "raw_json_ok": False,
            "model_has_evidence": None,
            "citation_numbers": [],
            "invalid_citation": False,
            "final_has_evidence": False,
            "answer": f"模型调用失败：{error}",
            "keyword_hit": None,
            "latency": round(time.perf_counter() - started, 2),
        }

    model_answer = parse_model_answer(raw)
    answer, has_evidence = parse_answer(raw, len(matches))
    citations = (
        [int(number) for number in CITATION_PATTERN.findall(model_answer.answer)]
        if model_answer is not None
        else []
    )
    invalid_citation = any(
        number < 1 or number > len(matches) for number in citations
    )
    keyword_hit = (
        any(keyword in answer for keyword in expected) if expected and has_evidence else None
    )

    return {
        "question": item["question"],
        "type": item["type"],
        "matches": len(matches),
        "retrieval_expected_keyword_hit": retrieval_keyword_hit,
        "raw_json_ok": model_answer is not None,
        "model_has_evidence": model_answer.has_evidence if model_answer else None,
        "citation_numbers": citations,
        "invalid_citation": invalid_citation,
        "final_has_evidence": has_evidence,
        "answer": answer,
        "keyword_hit": keyword_hit,
        "latency": round(time.perf_counter() - started, 2),
    }


def summarize(rows):
    answerable = [row for row in rows if row["type"] in {"answerable", "partial"}]
    unanswerable = [row for row in rows if row["type"] == "unanswerable"]
    kept = [row for row in answerable if row["final_has_evidence"]]

    json_fail = [row for row in rows if row["raw_json_ok"] is False]
    no_citation = [
        row
        for row in answerable
        if row["model_has_evidence"] and not row["citation_numbers"]
    ]
    invalid_citation = [row for row in answerable if row["invalid_citation"]]
    keyword_miss = [row for row in kept if row["keyword_hit"] is False]
    retrieval_checked = [row for row in rows if row["retrieval_expected_keyword_hit"] is not None]
    retrieval_miss = [row for row in retrieval_checked if not row["retrieval_expected_keyword_hit"]]
    answered_unanswerable = [row for row in unanswerable if row["final_has_evidence"]]

    return {
        "answerable_total": len(answerable),
        "answerable_kept": len(kept),
        "answerable_refused": len(answerable) - len(kept),
        "answerable_refusal_rate": round(
            (len(answerable) - len(kept)) / len(answerable), 3
        ),
        "keyword_miss_rate": round(len(keyword_miss) / len(kept), 3) if kept else 0,
        "retrieval_expected_keyword_hit_rate": round(
            (len(retrieval_checked) - len(retrieval_miss)) / len(retrieval_checked), 3
        ) if retrieval_checked else None,
        "no_citation_with_evidence": len(no_citation),
        "invalid_citation": len(invalid_citation),
        "unanswerable_total": len(unanswerable),
        "unanswerable_refused": len(unanswerable) - len(answered_unanswerable),
        "unanswerable_false_answer": len(answered_unanswerable),
        "raw_json_failures": len(json_fail),
        "avg_latency": round(
            sum(row["latency"] for row in rows) / len(rows), 2
        ),
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if "--cleanup" in sys.argv:
        db = SessionLocal()
        try:
            result = cleanup_eval_scope(db)
        finally:
            db.close()
        print(
            "已清理评测数据："
            f"群组 {result['groups']} 个，文档 {result['documents']} 篇，"
            f"会话 {result['sessions']} 条，"
            f"用户{'已删除' if result['user_deleted'] else '不存在'}"
        )
        return

    db = SessionLocal()
    try:
        user, knowledge_base = reset_eval_scope(db)
        seed_documents(db, user, knowledge_base)

        rows = []
        for item in QUESTIONS:
            row = evaluate_one(db, user, knowledge_base, item)
            rows.append(row)
            print(
                f"[{row['type']}] {row['question']} -> "
                f"保留={row['final_has_evidence']} 引用={row['citation_numbers']} "
                f"命中={row['keyword_hit']} {row['latency']}s"
            )
            print(f"    {row['answer'][:120]}")
    finally:
        db.close()

    summary = summarize(rows)
    print("\n===== 汇总 =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    output_dir = ROOT / "storage" / "eval"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"rag_eval_{datetime.now():%Y%m%d_%H%M%S}.json"
    output_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().astimezone().isoformat(),
                "model": settings.llm_model,
                "question_count": len(QUESTIONS),
                "metrics_note": "检索关键词命中是固定评测集代理指标，不等同于人工相关性判断或通用检索召回率。",
                "summary": summary,
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n明细已写入 {output_path}")


if __name__ == "__main__":
    main()
