async def test_register_sets_cookie_and_returns_user(client):
    r = await client.post("/api/auth/register",
                          json={"username": "alice", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["username"] == "alice"
    assert "token" in r.cookies


async def test_register_duplicate_username_409(client):
    body = {"username": "bob", "password": "password123"}
    await client.post("/api/auth/register", json=body)
    r = await client.post("/api/auth/register", json=body)
    assert r.status_code == 409


async def test_login_success_and_wrong_password(client):
    body = {"username": "carol", "password": "password123"}
    await client.post("/api/auth/register", json=body)
    ok = await client.post("/api/auth/login", json=body)
    assert ok.status_code == 200
    assert "token" in ok.cookies
    bad = await client.post("/api/auth/login",
                            json={"username": "carol", "password": "wrongpass"})
    assert bad.status_code == 401


async def test_me_requires_auth(client):
    anon = await client.get("/api/auth/me")
    assert anon.status_code == 401
    await client.post("/api/auth/register",
                      json={"username": "dave", "password": "password123"})
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "dave"


async def test_logout_clears_cookie(client):
    await client.post("/api/auth/register",
                      json={"username": "erin", "password": "password123"})
    r = await client.post("/api/auth/logout")
    assert r.status_code == 200
    me = await client.get("/api/auth/me")
    assert me.status_code == 401
