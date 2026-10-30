import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client():
    main.store = main.TodoStore()  # fresh store per test
    return TestClient(main.app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_get(client):
    r = client.post("/todos", json={"title": "Write tests"})
    assert r.status_code == 201
    todo = r.json()
    assert todo == {"id": 1, "title": "Write tests", "done": False}
    assert client.get("/todos/1").json() == todo


def test_list_filters_by_done(client):
    client.post("/todos", json={"title": "a"})
    client.post("/todos", json={"title": "b", "done": True})
    assert len(client.get("/todos").json()) == 2
    assert [t["title"] for t in client.get("/todos?done=true").json()] == ["b"]
    assert [t["title"] for t in client.get("/todos?done=false").json()] == ["a"]


def test_patch_updates_only_given_fields(client):
    client.post("/todos", json={"title": "Ship it"})
    r = client.patch("/todos/1", json={"done": True})
    assert r.status_code == 200
    assert r.json() == {"id": 1, "title": "Ship it", "done": True}


def test_delete(client):
    client.post("/todos", json={"title": "temp"})
    assert client.delete("/todos/1").status_code == 204
    assert client.get("/todos/1").status_code == 404


def test_ids_are_not_reused_after_delete(client):
    client.post("/todos", json={"title": "one"})
    client.delete("/todos/1")
    assert client.post("/todos", json={"title": "two"}).json()["id"] == 2


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_missing_todo_returns_404(client, method):
    kwargs = {"json": {"done": True}} if method == "patch" else {}
    r = getattr(client, method)("/todos/999", **kwargs)
    assert r.status_code == 404
    assert r.json()["detail"] == "Todo 999 not found"


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "x" * 201}, {"title": 123}])
def test_create_rejects_invalid_input(client, body):
    assert client.post("/todos", json=body).status_code == 422


def test_patch_with_null_fields_leaves_them_unchanged(client):
    client.post("/todos", json={"title": "keep me"})
    r = client.patch("/todos/1", json={"title": None, "done": None})
    assert r.status_code == 200
    assert r.json() == {"id": 1, "title": "keep me", "done": False}


def test_patch_rejects_empty_title(client):
    client.post("/todos", json={"title": "keep me"})
    assert client.patch("/todos/1", json={"title": ""}).status_code == 422
