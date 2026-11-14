def test_create_group_with_default_knowledge_base(client, make_user):
    user = make_user("boss")

    response = client.post(
        "/api/groups",
        headers=user["headers"],
        json={"name": "新业务部", "group_type": "department"},
    )

    assert response.status_code == 201
    group = response.json()
    assert group["role"] == "admin"

    knowledge_bases = client.get(
        "/api/knowledge-bases", headers=user["headers"]
    ).json()
    assert any(kb["group_id"] == group["id"] for kb in knowledge_bases)


def test_member_management_and_last_admin_protection(
    client, make_user, make_group
):
    admin = make_user("admin")
    member = make_user("member")
    group_id, _ = make_group("成员管理部", admin["id"])

    added = client.post(
        f"/api/groups/{group_id}/members",
        headers=admin["headers"],
        json={"username": member["username"], "role": "editor"},
    )
    assert added.status_code == 201
    assert added.json()["role"] == "editor"

    duplicate = client.post(
        f"/api/groups/{group_id}/members",
        headers=admin["headers"],
        json={"username": member["username"], "role": "member"},
    )
    assert duplicate.status_code == 409

    outsider = make_user("outsider")
    forbidden = client.post(
        f"/api/groups/{group_id}/members",
        headers=member["headers"],
        json={"username": outsider["username"]},
    )
    assert forbidden.status_code == 403

    promoted = client.patch(
        f"/api/groups/{group_id}/members/{member['id']}",
        headers=admin["headers"],
        json={"role": "admin"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    demoted_self = client.patch(
        f"/api/groups/{group_id}/members/{admin['id']}",
        headers=admin["headers"],
        json={"role": "member"},
    )
    assert demoted_self.status_code == 200

    last_admin_demote = client.patch(
        f"/api/groups/{group_id}/members/{member['id']}",
        headers=member["headers"],
        json={"role": "member"},
    )
    assert last_admin_demote.status_code == 409

    last_admin_remove = client.delete(
        f"/api/groups/{group_id}/members/{member['id']}",
        headers=member["headers"],
    )
    assert last_admin_remove.status_code == 409


def test_personal_knowledge_base_created_once(client, make_user):
    user = make_user("solo")

    first = client.post(
        "/api/knowledge-bases",
        headers=user["headers"],
        json={"name": "我的个人库", "scope_type": "personal"},
    )
    assert first.status_code == 201
    assert first.json()["owner_user_id"] == user["id"]

    second = client.post(
        "/api/knowledge-bases",
        headers=user["headers"],
        json={"name": "第二个个人库", "scope_type": "personal"},
    )
    assert second.status_code == 409


def test_enterprise_knowledge_base_permissions(client, make_user, make_group, add_member):
    owner = make_user("owner")
    member = make_user("member")
    outsider = make_user("outsider")
    group_id, _ = make_group("知识库权限部", owner["id"])
    add_member(group_id, member["id"], "member")

    assert (
        client.post(
            "/api/knowledge-bases",
            headers=outsider["headers"],
            json={
                "name": "越权知识库",
                "scope_type": "enterprise_group",
                "group_id": group_id,
            },
        ).status_code
        == 404
    )

    assert (
        client.post(
            "/api/knowledge-bases",
            headers=member["headers"],
            json={
                "name": "成员建库",
                "scope_type": "enterprise_group",
                "group_id": group_id,
            },
        ).status_code
        == 403
    )

    assert (
        client.post(
            "/api/knowledge-bases",
            headers=owner["headers"],
            json={
                "name": "重复知识库",
                "scope_type": "enterprise_group",
                "group_id": group_id,
            },
        ).status_code
        == 409
    )


def test_rename_and_delete_knowledge_base(client, make_user):
    user = make_user("owner")
    created = client.post(
        "/api/knowledge-bases",
        headers=user["headers"],
        json={"name": "旧名字", "scope_type": "personal"},
    ).json()

    renamed = client.patch(
        f"/api/knowledge-bases/{created['id']}",
        headers=user["headers"],
        json={"name": "新名字"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "新名字"

    document = client.post(
        f"/api/knowledge-bases/{created['id']}/documents",
        headers=user["headers"],
        json={"title": "占位文档", "content": "内容"},
    ).json()

    assert (
        client.delete(
            f"/api/knowledge-bases/{created['id']}", headers=user["headers"]
        ).status_code
        == 409
    )

    client.delete(f"/api/documents/{document['id']}", headers=user["headers"])
    assert (
        client.delete(
            f"/api/knowledge-bases/{created['id']}", headers=user["headers"]
        ).status_code
        == 204
    )


def test_delete_knowledge_base_with_chat_sessions(client, make_user):
    user = make_user("kb_session_owner")
    created = client.post(
        "/api/knowledge-bases",
        headers=user["headers"],
        json={"name": "有会话的个人库", "scope_type": "personal"},
    ).json()

    asked = client.post(
        f"/api/knowledge-bases/{created['id']}/ask",
        headers=user["headers"],
        json={"question": "还没有资料时提问"},
    )
    assert asked.status_code == 200
    assert client.get("/api/chat/sessions", headers=user["headers"]).json()

    deleted = client.delete(
        f"/api/knowledge-bases/{created['id']}", headers=user["headers"]
    )
    assert deleted.status_code == 204
    assert client.get("/api/chat/sessions", headers=user["headers"]).json() == []


def test_search_users_by_prefix(client, make_user):
    alice = make_user("searchalice")
    bob = make_user("searchbob")

    results = client.get(
        f"/api/users?username={alice['username'][:9]}", headers=bob["headers"]
    ).json()

    assert any(user["username"] == alice["username"] for user in results)
    assert client.get("/api/users?username=a", headers=bob["headers"]).json() == []
    assert client.get("/api/users?username=%25%25", headers=bob["headers"]).json() == []
