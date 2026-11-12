from models.knowledge_group import GroupMember
from services.retrieval import distance_to_score


def test_distance_to_score_converts_normalized_l2():
    assert distance_to_score(0) == 1.0
    assert distance_to_score(0.5) == 0.75
    assert distance_to_score(2) == 0.0
    assert distance_to_score(2.5) == 0.0


def test_search_returns_relevant_chunk(client, make_user, make_group):
    owner = make_user("owner")
    _, knowledge_base_id = make_group("检索测试部", owner["id"])

    client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents",
        headers=owner["headers"],
        json={
            "title": "差旅管理制度",
            "content": "员工出差住宿标准：一线城市每晚不超过 600 元，报销需提供发票。",
        },
    )

    response = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/search",
        headers=owner["headers"],
        json={"question": "出差住宿报销标准是多少"},
    )

    assert response.status_code == 200
    matches = response.json()["matches"]
    assert matches
    assert matches[0]["document_title"] == "差旅管理制度"
    assert "住宿" in matches[0]["content"]
    assert 0 <= matches[0]["score"] <= 1


def test_search_rejects_knowledge_base_without_access(client, make_user, make_group):
    owner = make_user("owner")
    outsider = make_user("outsider")
    _, knowledge_base_id = make_group("私有部门", owner["id"])

    response = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/search",
        headers=outsider["headers"],
        json={"question": "任何问题"},
    )

    assert response.status_code == 404


def test_search_stops_after_member_removed(client, make_user, make_group, add_member, db):
    owner = make_user("owner")
    member = make_user("member")
    group_id, knowledge_base_id = make_group("动态权限部", owner["id"])
    add_member(group_id, member["id"], "member")

    client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents",
        headers=owner["headers"],
        json={"title": "值班制度", "content": "值班人员需要提前十分钟到岗。"},
    )

    allowed = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/search",
        headers=member["headers"],
        json={"question": "值班要提前多久到岗"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["matches"]

    db.query(GroupMember).filter_by(
        group_id=group_id, user_id=member["id"]
    ).delete()
    db.commit()

    denied = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/search",
        headers=member["headers"],
        json={"question": "值班要提前多久到岗"},
    )
    assert denied.status_code == 404


def test_search_isolated_between_knowledge_bases(client, make_user, make_group):
    owner = make_user("owner")
    other = make_user("other")
    _, knowledge_base_a = make_group("甲部门", owner["id"])
    _, knowledge_base_b = make_group("乙部门", other["id"])

    client.post(
        f"/api/knowledge-bases/{knowledge_base_a}/documents",
        headers=owner["headers"],
        json={"title": "甲部门制度", "content": "甲部门专属的保密内容。"},
    )

    response = client.post(
        f"/api/knowledge-bases/{knowledge_base_b}/search",
        headers=other["headers"],
        json={"question": "甲部门保密内容"},
    )

    assert response.status_code == 200
    assert response.json()["matches"] == []
