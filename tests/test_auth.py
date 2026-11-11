def test_register_login_and_me(client, make_user):
    user = make_user("alice")

    response = client.get("/api/auth/me", headers=user["headers"])

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == user["username"]
    assert "password_hash" not in body


def test_wrong_password_returns_401(client, make_user):
    user = make_user("alice")

    response = client.post(
        "/api/auth/login",
        json={"username": user["username"], "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_duplicate_username_returns_409(client, make_user):
    user = make_user("alice")

    response = client.post(
        "/api/auth/register",
        json={"username": user["username"], "password": "Passw0rd!"},
    )

    assert response.status_code == 409


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_invalid_token_returns_401(client):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
