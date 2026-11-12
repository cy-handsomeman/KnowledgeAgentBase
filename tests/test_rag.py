import json

from services.rag import NO_EVIDENCE_ANSWER, parse_answer, parse_model_answer


def _payload(answer: str, has_evidence: bool = True) -> str:
    return json.dumps(
        {"answer": answer, "has_evidence": has_evidence}, ensure_ascii=False
    )


def test_parse_answer_accepts_valid_citation():
    raw = _payload("一线城市住宿标准为每晚不超过 600 元 [1]。")
    answer, has_evidence = parse_answer(raw, 2)
    assert has_evidence is True
    assert answer == "一线城市住宿标准为每晚不超过 600 元 [1]。"


def test_parse_answer_accepts_fenced_json():
    raw = "```json\n" + _payload("答案是 600 元 [1]") + "\n```"
    answer, has_evidence = parse_answer(raw, 1)
    assert has_evidence is True
    assert "600" in answer


def test_parse_answer_rejects_missing_citation():
    answer, has_evidence = parse_answer(_payload("住宿标准是 600 元。"), 2)
    assert (answer, has_evidence) == (NO_EVIDENCE_ANSWER, False)


def test_parse_answer_rejects_out_of_range_citation():
    answer, has_evidence = parse_answer(_payload("住宿标准是 600 元 [3]。"), 2)
    assert (answer, has_evidence) == (NO_EVIDENCE_ANSWER, False)


def test_parse_answer_rejects_when_model_flags_no_evidence():
    answer, has_evidence = parse_answer(_payload("住宿标准是 600 元 [1]", False), 2)
    assert (answer, has_evidence) == (NO_EVIDENCE_ANSWER, False)


def test_parse_answer_rejects_invalid_json():
    assert parse_model_answer("这不是 JSON") is None
    assert parse_answer("这不是 JSON", 2) == (NO_EVIDENCE_ANSWER, False)
