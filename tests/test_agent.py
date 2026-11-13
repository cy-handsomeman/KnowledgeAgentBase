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

    session_id, answer, sources, has_evidence, steps, _ = run_agent(
        db, user["id"], kb_id, "住宿标准是多少？", None
    )
    assert session_id
    assert has_evidence is True
    assert "[1]" in answer
    assert sources[0].document_title == "差旅制度"
    assert len(steps) == 1 and steps[0].result_count == 1


def test_agent_rejects_unauthorized_knowledge_base(db, make_user, make_personal_kb):
    owner = make_user("agent_kb_owner")
    outsider = make_user("agent_kb_outsider")
    kb_id = make_personal_kb(owner["id"])
    with pytest.raises(PermissionError):
        run_agent(db, outsider["id"], kb_id, "不该访问", None)
