import pytest
from pydantic import ValidationError

from schemas.agent import AgentRequest
from services.agent import (
    MAX_TOOL_CALLS,
    SearchArguments,
    TOOL_NAME,
    validate_tool_call,
    within_tool_budget,
)
from services.llm import LLMError
from schemas.search import SearchMatch
from services.agent import run_agent
from models.chat import ChatSession


def test_agent_request_validates_question_and_session():
    request = AgentRequest(question="查一下差旅标准", session_id=3)
    assert request.question == "查一下差旅标准"
    assert request.session_id == 3


def test_search_tool_arguments_are_bounded_and_strict():
    assert SearchArguments.model_validate({"query": "报销期限", "top_k": 3}).top_k == 3
    with pytest.raises(ValidationError):
        SearchArguments.model_validate({"query": "x", "top_k": 6})
    with pytest.raises(ValidationError):
        SearchArguments.model_validate({"query": "x", "url": "https://example.com"})
    with pytest.raises(ValidationError):
        SearchArguments.model_validate({"query": "x", "top_k": "2"})


def test_agent_loop_has_bounded_allowlisted_tool_surface():
    from services.agent import SEARCH_TOOL

    assert MAX_TOOL_CALLS == 3
    assert SEARCH_TOOL["function"]["name"] == TOOL_NAME
    assert SEARCH_TOOL["function"]["parameters"]["additionalProperties"] is False
    assert within_tool_budget(0, 1)
    assert within_tool_budget(2, 1)
    assert not within_tool_budget(3, 1)
    assert not within_tool_budget(0, 0)


def test_agent_rejects_unknown_tool_and_malformed_arguments():
    with pytest.raises(LLMError):
        validate_tool_call({"id": "x", "function": {"name": "drop_database", "arguments": "{}"}})
    with pytest.raises(LLMError):
        validate_tool_call({"id": "x", "function": {"name": TOOL_NAME, "arguments": "not-json"}})


def test_agent_executes_search_then_returns_valid_citation(
    db, make_user, make_personal_kb, monkeypatch
):
    from services import agent

    user = make_user("agent_owner")
    kb_id = make_personal_kb(user["id"])
    responses = iter([
        {"tool_calls": [{
            "id": "call-1",
            "function": {
                "name": TOOL_NAME,
                "arguments": '{"query":"差旅住宿"}',
            },
        }]},
        {"content": '{"answer":"一线城市每晚不超过 600 元 [1]。","has_evidence":true}'},
    ])
    monkeypatch.setattr(agent, "chat_completion_message", lambda *a, **k: next(responses))
    monkeypatch.setattr(
        agent,
        "retrieve_matches",
        lambda *a, **k: [SearchMatch(
            document_id=9, document_title="差旅制度", chunk_id=12,
            chunk_index=0, page_number=2, content="住宿标准为每晚 600 元。", score=0.9,
        )],
    )

    session_id, answer, sources, has_evidence, steps, model_calls, elapsed, limited, _ = run_agent(
        db, user["id"], kb_id, "住宿标准是多少？", None
    )
    assert session_id
    assert has_evidence is True
    assert "[1]" in answer
    assert sources[0].document_title == "差旅制度"
    assert len(steps) == 1 and steps[0].result_count == 1
    assert model_calls == 2
    assert elapsed >= 0
    assert not limited


def test_agent_rejects_unauthorized_knowledge_base(db, make_user, make_personal_kb):
    owner = make_user("agent_kb_owner")
    outsider = make_user("agent_kb_outsider")
    kb_id = make_personal_kb(owner["id"])
    with pytest.raises(PermissionError):
        run_agent(db, outsider["id"], kb_id, "不该访问", None)


def test_agent_abstains_when_retrieval_has_no_results(
    db, make_user, make_personal_kb, monkeypatch
):
    from services import agent

    user = make_user("agent_empty")
    kb_id = make_personal_kb(user["id"])
    responses = iter([
        {"tool_calls": [{"id": "call-1", "function": {
            "name": TOOL_NAME, "arguments": '{"query":"无匹配资料"}',
        }}]},
        {"content": '{"answer":"无法回答","has_evidence":false}'},
    ])
    monkeypatch.setattr(agent, "chat_completion_message", lambda *a, **k: next(responses))
    monkeypatch.setattr(agent, "retrieve_matches", lambda *a, **k: [])
    _, answer, sources, has_evidence, steps, _, _, limited, _ = run_agent(
        db, user["id"], kb_id, "无匹配资料", None
    )
    assert not has_evidence
    assert answer == "根据现有资料无法回答。"
    assert sources == []
    assert steps[0].result_count == 0
    assert not limited


def test_agent_stops_after_tool_budget_and_rejects_invalid_citation(
    db, make_user, make_personal_kb, monkeypatch
):
    from services import agent

    user = make_user("agent_limit")
    kb_id = make_personal_kb(user["id"])
    tool_reply = {"tool_calls": [{"id": "call", "function": {
        "name": TOOL_NAME, "arguments": '{"query":"q"}',
    }}]}
    replies = iter([tool_reply, tool_reply, tool_reply, tool_reply])
    monkeypatch.setattr(agent, "chat_completion_message", lambda *a, **k: next(replies))
    monkeypatch.setattr(agent, "retrieve_matches", lambda *a, **k: [SearchMatch(
        document_id=9, document_title="制度", chunk_id=12, chunk_index=0,
        page_number=None, content="内容", score=0.9,
    )])
    _, answer, sources, has_evidence, steps, model_calls, _, limited, _ = run_agent(
        db, user["id"], kb_id, "q", None
    )
    assert not has_evidence
    assert answer == "根据现有资料无法回答。"
    assert not sources
    assert len(steps) == MAX_TOOL_CALLS
    assert model_calls == MAX_TOOL_CALLS + 1
    assert limited

    # A cited number outside the retrieved set must be reduced to abstention.
    citation_replies = iter([
        tool_reply,
        {"content": '{"answer":"无效引用 [2]","has_evidence":true}'},
    ])
    monkeypatch.setattr(agent, "chat_completion_message", lambda *a, **k: next(citation_replies))
    _, answer, sources, has_evidence, _, _, _, _, _ = run_agent(
        db, user["id"], kb_id, "q2", None
    )
    assert not has_evidence and not sources
    assert answer == "根据现有资料无法回答。"


def test_agent_wraps_tool_failures_and_checks_session_ownership(
    db, make_user, make_personal_kb, make_group, monkeypatch
):
    from services import agent

    user = make_user("agent_tool_error")
    other = make_user("agent_session_other")
    kb_id = make_personal_kb(user["id"])
    session = ChatSession(
        user_id=other["id"], title="other", scope_type="personal", knowledge_base_id=kb_id
    )
    db.add(session)
    db.commit()
    with pytest.raises(ValueError):
        agent._history(db, session.id, user["id"], kb_id)
    own_session = ChatSession(
        user_id=user["id"], title="own", scope_type="personal", knowledge_base_id=kb_id
    )
    db.add(own_session)
    db.commit()
    another_kb_id = make_group("Agent 另一个部", user["id"])[1]
    with pytest.raises(ValueError):
        agent._history(db, own_session.id, user["id"], another_kb_id)

    monkeypatch.setattr(agent, "chat_completion_message", lambda *a, **k: {
        "tool_calls": [{"id": "call-1", "function": {
            "name": TOOL_NAME, "arguments": '{"query":"q"}',
        }}],
    })
    monkeypatch.setattr(agent, "retrieve_matches", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("private detail")))
    with pytest.raises(LLMError, match="知识库检索工具执行失败"):
        run_agent(db, user["id"], kb_id, "q", None)


def test_agent_reports_tool_deadline_as_safe_error(
    db, make_user, make_personal_kb, monkeypatch
):
    from services import agent

    user = make_user("agent_timeout")
    kb_id = make_personal_kb(user["id"])
    monkeypatch.setattr(agent, "chat_completion_message", lambda *a, **k: {
        "tool_calls": [{"id": "call-1", "function": {
            "name": TOOL_NAME, "arguments": '{"query":"q"}',
        }}],
    })
    monkeypatch.setattr(agent, "retrieve_matches", lambda *a, **k: [])
    monkeypatch.setattr(agent, "TOOL_DEADLINE_SECONDS", -1)
    with pytest.raises(LLMError, match="超过单次工具执行时限"):
        run_agent(db, user["id"], kb_id, "q", None)


def test_agent_rejects_non_string_final_response(
    db, make_user, make_personal_kb, monkeypatch
):
    from services import agent

    user = make_user("agent_invalid_response")
    kb_id = make_personal_kb(user["id"])
    responses = iter([
        {"tool_calls": [{"id": "call-1", "function": {
            "name": TOOL_NAME, "arguments": '{"query":"q"}',
        }}]},
        {"content": {"answer": "无效响应"}},
    ])
    monkeypatch.setattr(agent, "chat_completion_message", lambda *a, **k: next(responses))
    monkeypatch.setattr(agent, "retrieve_matches", lambda *a, **k: [SearchMatch(
        document_id=9, document_title="制度", chunk_id=12, chunk_index=0,
        page_number=None, content="内容", score=0.9,
    )])

    with pytest.raises(LLMError, match="大模型返回格式异常") as exc_info:
        run_agent(db, user["id"], kb_id, "q", None)
    assert "无效响应" not in str(exc_info.value)


def test_agent_enforces_total_deadline_before_model_call(
    db, make_user, make_personal_kb, monkeypatch
):
    from services import agent

    user = make_user("agent_total_deadline")
    kb_id = make_personal_kb(user["id"])
    monkeypatch.setattr(agent, "AGENT_DEADLINE_SECONDS", 0)

    def unexpected_model_call(*args, **kwargs):
        raise AssertionError("超过总时限后不应调用模型")

    monkeypatch.setattr(agent, "chat_completion_message", unexpected_model_call)
    with pytest.raises(LLMError, match="Agent 执行超过总时限"):
        run_agent(db, user["id"], kb_id, "q", None)


def test_agent_bounds_model_timeout_by_remaining_budget(
    db, make_user, make_personal_kb, monkeypatch
):
    from services import agent

    user = make_user("agent_model_timeout")
    kb_id = make_personal_kb(user["id"])
    monkeypatch.setattr(agent, "AGENT_DEADLINE_SECONDS", 10)
    captured = {}

    def model_reply(*args, **kwargs):
        captured.update(kwargs)
        return {"content": ""}

    monkeypatch.setattr(agent, "chat_completion_message", model_reply)
    run_agent(db, user["id"], kb_id, "q", None)
    assert 0 < captured["timeout"] <= 10


def test_agent_run_refreshes_session_order_timestamp(
    db, make_user, make_personal_kb, monkeypatch
):
    from datetime import datetime

    from models.chat import ChatSession
    from services import agent

    user = make_user("agent_session_time")
    kb_id = make_personal_kb(user["id"])
    session = ChatSession(
        user_id=user["id"], title="旧会话", scope_type="personal",
        knowledge_base_id=kb_id, updated_at=datetime(2020, 1, 1),
    )
    db.add(session)
    db.commit()
    monkeypatch.setattr(agent, "chat_completion_message", lambda *a, **k: {"content": ""})
    monkeypatch.setattr(agent, "retrieve_matches", lambda *a, **k: [])

    run_agent(db, user["id"], kb_id, "继续提问", session.id)
    db.refresh(session)
    assert session.updated_at > datetime(2020, 1, 1)


def test_llm_error_hides_upstream_body_and_credentials(monkeypatch):
    from services import llm

    class Response:
        status_code = 502
        text = "上游敏感正文"

    monkeypatch.setattr(llm.settings, "llm_api_key", "测试凭据")
    monkeypatch.setattr(llm.httpx, "post", lambda *args, **kwargs: Response())

    with pytest.raises(LLMError) as exc_info:
        llm.chat_completion_message([{"role": "user", "content": "q"}])

    message = str(exc_info.value)
    assert "502" in message
    assert "上游敏感正文" not in message
    assert "测试凭据" not in message
