def test_download_uploaded_txt(client, make_user, make_group):
    owner = make_user("owner")
    other = make_user("other")
    _, knowledge_base_id = make_group("下载测试部", owner["id"])

    document = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents/upload",
        headers=owner["headers"],
        files={"file": ("制度.txt", "下载内容".encode("utf-8"), "text/plain")},
    ).json()

    response = client.get(
        f"/api/documents/{document['id']}/download", headers=owner["headers"]
    )
    assert response.status_code == 200
    assert "下载内容" in response.content.decode("utf-8")

    inline = client.get(
        f"/api/documents/{document['id']}/download?inline=true",
        headers=owner["headers"],
    )
    assert inline.status_code == 200
    assert "inline" in inline.headers.get("content-disposition", "")

    assert (
        client.get(
            f"/api/documents/{document['id']}/download", headers=other["headers"]
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/documents/{document['id']}/download").status_code == 401
    )


def test_download_online_document_returns_400(client, make_user, make_group):
    owner = make_user("owner")
    _, knowledge_base_id = make_group("在线文档部", owner["id"])

    document = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents",
        headers=owner["headers"],
        json={"title": "在线文档", "content": "正文"},
    ).json()

    response = client.get(
        f"/api/documents/{document['id']}/download", headers=owner["headers"]
    )
    assert response.status_code == 400
