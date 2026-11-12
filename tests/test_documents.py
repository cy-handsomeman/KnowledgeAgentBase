from pathlib import Path


def test_document_crud(client, make_user, make_group):
    owner = make_user("owner")
    _, knowledge_base_id = make_group("文档测试部", owner["id"])

    created = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents",
        headers=owner["headers"],
        json={"title": "差旅制度", "content": "住宿标准 600 元。"},
    )
    assert created.status_code == 201
    document = created.json()
    assert document["status"] == "READY"
    assert document["file_type"] == "markdown"

    listed = client.get(
        f"/api/knowledge-bases/{knowledge_base_id}/documents",
        headers=owner["headers"],
    ).json()
    assert len(listed) == 1
    assert "content" not in listed[0]

    updated = client.put(
        f"/api/documents/{document['id']}",
        headers=owner["headers"],
        json={"content": "住宿标准 800 元。"},
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == "住宿标准 800 元。"

    deleted = client.delete(
        f"/api/documents/{document['id']}",
        headers=owner["headers"],
    )
    assert deleted.status_code == 204
    assert (
        client.get(
            f"/api/documents/{document['id']}", headers=owner["headers"]
        ).status_code
        == 404
    )


def test_upload_txt_and_delete_file(client, make_user, make_group):
    owner = make_user("owner")
    _, knowledge_base_id = make_group("上传测试部", owner["id"])

    response = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents/upload",
        headers=owner["headers"],
        files={"file": ("员工手册.txt", "员工手册内容".encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 201
    document = response.json()
    assert document["file_type"] == "txt"
    assert document["status"] == "READY"
    file_path = Path(document["file_path"])
    assert file_path.is_file()

    deleted = client.delete(
        f"/api/documents/{document['id']}", headers=owner["headers"]
    )
    assert deleted.status_code == 204
    assert not file_path.exists()


def test_upload_rejects_exe_and_oversize(client, make_user, make_group):
    owner = make_user("owner")
    _, knowledge_base_id = make_group("上传校验部", owner["id"])

    exe = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents/upload",
        headers=owner["headers"],
        files={"file": ("malware.exe", b"fake", "application/octet-stream")},
    )
    assert exe.status_code == 400

    oversize = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents/upload",
        headers=owner["headers"],
        files={
            "file": (
                "big.txt",
                b"a" * (10 * 1024 * 1024 + 1),
                "text/plain",
            )
        },
    )
    assert oversize.status_code == 413


def test_upload_requires_edit_permission(client, make_user, make_group, add_member):
    owner = make_user("owner")
    member = make_user("member")
    group_id, knowledge_base_id = make_group("上传权限部", owner["id"])
    add_member(group_id, member["id"], "member")

    response = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents/upload",
        headers=member["headers"],
        files={"file": ("制度.txt", "内容".encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 403


def test_failed_reindex_keeps_previous_index(client, make_user, make_group):
    owner = make_user("owner")
    _, knowledge_base_id = make_group("索引保护部", owner["id"])

    created = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents",
        headers=owner["headers"],
        json={"title": "住宿制度", "content": "住宿标准 600 元。"},
    )
    document = created.json()

    failed = client.put(
        f"/api/documents/{document['id']}",
        headers=owner["headers"],
        json={"content": "   "},
    )
    assert failed.status_code == 200
    body = failed.json()
    assert body["status"] == "READY"
    assert "重建索引失败" in body["error_message"]
    assert body["content"] == "住宿标准 600 元。"

    search = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/search",
        headers=owner["headers"],
        json={"question": "住宿标准是多少"},
    )
    assert search.status_code == 200
    matches = search.json()["matches"]
    assert matches
    assert "600" in matches[0]["content"]


def test_corrupt_pdf_marks_failed(client, make_user, make_group):
    owner = make_user("owner")
    _, knowledge_base_id = make_group("损坏文档部", owner["id"])

    response = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents/upload",
        headers=owner["headers"],
        files={"file": ("broken.pdf", b"this is not a pdf", "application/pdf")},
    )

    assert response.status_code == 201
    document = response.json()
    assert document["status"] == "FAILED"
    assert document["error_message"]
