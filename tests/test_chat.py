def test_chat_session_flow(client, make_user, make_group):
    owner = make_user("owner")
    _, knowledge_base_id = make_group("聊天测试部", owner["id"])

    response = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/ask",
        headers=owner["headers"],
        json={"question": "公司年假有多少天"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_evidence"] is False
    session_id = body["session_id"]

    sessions = client.get("/api/chat/sessions", headers=owner["headers"]).json()
    assert [session["id"] for session in sessions] == [session_id]

    messages = client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=owner["headers"]
    ).json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "公司年假有多少天"

    other = make_user("other")
    assert (
        client.get(
            f"/api/chat/sessions/{session_id}/messages", headers=other["headers"]
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/chat/sessions/{session_id}", headers=other["headers"]
        ).status_code
        == 404
    )

    assert (
        client.delete(
            f"/api/chat/sessions/{session_id}", headers=owner["headers"]
        ).status_code
        == 204
    )
    assert client.get("/api/chat/sessions", headers=owner["headers"]).json() == []


def test_ask_rejects_session_with_other_knowledge_base(
    client, make_user, make_group
):
    owner = make_user("owner")
    _, first_kb = make_group("甲部门", owner["id"])
    _, second_kb = make_group("乙部门", owner["id"])

    created = client.post(
        f"/api/knowledge-bases/{first_kb}/ask",
        headers=owner["headers"],
        json={"question": "第一个问题"},
    )
    assert created.status_code == 200

    response = client.post(
        f"/api/knowledge-bases/{second_kb}/ask",
        headers=owner["headers"],
        json={
            "question": "换个知识库",
            "session_id": created.json()["session_id"],
        },
    )
    assert response.status_code == 400
