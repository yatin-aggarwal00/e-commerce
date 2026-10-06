from tests.conftest import auth


def test_register_and_me(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "password123", "full_name": "A B"},
    )
    assert r.status_code == 201
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    me = client.get("/api/v1/auth/me", headers=auth(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "a@b.com"
    assert me.json()["is_admin"] is False


def test_duplicate_email_rejected(client):
    body = {"email": "dup@b.com", "password": "password123"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    assert client.post("/api/v1/auth/register", json=body).status_code == 409


def test_login_wrong_password(client):
    client.post("/api/v1/auth/register", json={"email": "c@b.com", "password": "password123"})
    r = client.post("/api/v1/auth/login", json={"email": "c@b.com", "password": "wrong"})
    assert r.status_code == 401


def test_refresh_token(client):
    reg = client.post(
        "/api/v1/auth/register", json={"email": "d@b.com", "password": "password123"}
    ).json()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": reg["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_refresh_rejects_access_token(client):
    reg = client.post(
        "/api/v1/auth/register", json={"email": "e@b.com", "password": "password123"}
    ).json()
    # Passing an access token where a refresh token is expected must fail.
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": reg["access_token"]})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_password_reset_request_is_non_enumerating(client):
    # Unknown email still returns 200 so attackers can't probe for accounts.
    r = client.post("/api/v1/auth/password-reset/request", json={"email": "nobody@x.com"})
    assert r.status_code == 200
