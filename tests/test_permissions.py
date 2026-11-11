def test_group_roles_and_document_permissions(
    client, make_user, make_group, add_member
):
    owner = make_user("owner")
    member = make_user("member")
    outsider = make_user("outsider")
    group_id, knowledge_base_id = make_group("权限测试部", owner["id"])
    add_member(group_id, member["id"], "member")

    groups = client.get("/api/groups", headers=member["headers"]).json()
    assert [(group["name"], group["role"]) for group in groups] == [
        ("权限测试部", "member")
    ]

    created = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents",
        headers=owner["headers"],
        json={"title": "部门制度", "content": "部门制度正文。"},
    )
    assert created.status_code == 201

    denied = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents",
        headers=member["headers"],
        json={"title": "成员不能创建"},
    )
    assert denied.status_code == 403

    assert (
        client.get(
            f"/api/knowledge-bases/{knowledge_base_id}/documents",
            headers=member["headers"],
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/knowledge-bases/{knowledge_base_id}/documents",
            headers=outsider["headers"],
        ).status_code
        == 404
    )


def test_personal_knowledge_base_isolation(client, make_user, make_personal_kb):
    owner = make_user("owner")
    other = make_user("other")
    knowledge_base_id = make_personal_kb(owner["id"])

    created = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents",
        headers=owner["headers"],
        json={"title": "私人笔记", "content": "只属于所有者。"},
    )
    assert created.status_code == 201
    document_id = created.json()["id"]

    assert (
        client.get(f"/api/documents/{document_id}", headers=other["headers"]).status_code
        == 404
    )
    assert (
        client.get(f"/api/documents/{document_id}", headers=owner["headers"]).status_code
        == 200
    )
