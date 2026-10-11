from fastapi.testclient import TestClient

from app.main import app


def test_frontend_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Kanban" in response.text


def test_openapi_schema(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/tasks" in paths
    assert "/api/v1/auth/login" in paths


def test_list_seeded_projects(client):
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 1
    assert projects[0]["id"] == 1


def test_register_success(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "newdev", "password": "pass123", "role": "developer"},
    )
    assert response.status_code == 201
    assert "newdev" in response.json()["message"]


def test_register_duplicate(client):
    payload = {"username": "newdev", "password": "pass123", "role": "developer"}
    client.post("/api/v1/auth/register", json=payload)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


def test_register_administrator_forbidden(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "evil", "password": "pass123", "role": "administrator"},
    )
    assert response.status_code == 403


def test_register_unknown_role_forbidden(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "evil2", "password": "pass123", "role": "root"},
    )
    assert response.status_code == 403


def test_register_short_username_validation(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "a", "password": "pass123", "role": "developer"},
    )
    assert response.status_code == 422


async def test_register_stores_hashed_password(client, db_session):
    from sqlalchemy import select

    from app.models.kanban import User

    client.post(
        "/api/v1/auth/register",
        json={"username": "hashdev", "password": "pass123", "role": "developer"},
    )
    user = await db_session.scalar(select(User).where(User.username == "hashdev"))
    assert user is not None
    assert user.hashed_password != "pass123"
    assert user.hashed_password.startswith("$2b$")


def test_login_returns_token(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["role"] == "administrator"
    assert data["access_token"]


def test_login_wrong_password(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "nope"}
    )
    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "ghost", "password": "nope"}
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_mutations_require_token(client):
    assert client.post("/api/v1/tasks", json={"title": "x", "column_id": 1}).status_code == 401
    assert client.post("/api/v1/columns", json={"title": "x"}).status_code == 401
    assert client.put("/api/v1/columns/1", json={"title": "x"}).status_code == 401
    assert client.put("/api/v1/tasks/1", json={"title": "x"}).status_code == 401
    assert client.delete("/api/v1/tasks/1").status_code == 401
    assert client.post(
        "/api/v1/tasks/1/comments", json={"text": "x", "author": "y"}
    ).status_code == 401
    assert client.post("/api/v1/projects", json={"title": "x"}).status_code == 401
    assert client.put("/api/v1/projects/1", json={"title": "x"}).status_code == 401
    assert client.delete("/api/v1/projects/1").status_code == 401
    assert client.delete("/api/v1/columns/1").status_code == 401


def test_invalid_token_rejected(client):
    headers = {"Authorization": "Bearer broken.token.value"}
    response = client.post(
        "/api/v1/tasks", json={"title": "x", "column_id": 1}, headers=headers
    )
    assert response.status_code == 401


def test_wrong_scheme_header_rejected(client):
    headers = {"Authorization": "Basic YWRtaW46YWRtaW4="}
    response = client.get("/api/v1/projects", headers=headers)
    assert response.status_code == 200


def test_project_create_requires_role(client, developer_headers, admin_headers):
    assert (
        client.post("/api/v1/projects", json={"title": "P"}, headers=developer_headers).status_code
        == 403
    )
    response = client.post(
        "/api/v1/projects",
        json={"title": "Второй", "description": "Описание"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["id"] > 1


def test_project_manager_can_create_and_update(client, manager_headers):
    created = client.post(
        "/api/v1/projects", json={"title": "Manager project"}, headers=manager_headers
    )
    assert created.status_code == 201
    updated = client.put(
        f"/api/v1/projects/{created.json()['id']}",
        json={"title": "Обновлён"},
        headers=manager_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Обновлён"


def test_project_update_validation(client, admin_headers):
    response = client.put(
        "/api/v1/projects/1", json={"title": "   "}, headers=admin_headers
    )
    assert response.status_code == 422


def test_project_update_not_found(client, admin_headers):
    response = client.put(
        "/api/v1/projects/9999", json={"title": "x"}, headers=admin_headers
    )
    assert response.status_code == 404


def test_project_delete_admin_only(client, admin_headers, manager_headers, developer_headers):
    assert (
        client.delete("/api/v1/projects/1", headers=manager_headers).status_code == 403
    )
    assert (
        client.delete("/api/v1/projects/1", headers=developer_headers).status_code == 403
    )
    response = client.delete("/api/v1/projects/1", headers=admin_headers)
    assert response.status_code == 200
    assert client.get("/api/v1/projects").json() == []


def test_project_delete_cascades_columns(client, admin_headers):
    client.delete("/api/v1/projects/1", headers=admin_headers)
    assert client.get("/api/v1/columns").json() == []
    assert client.get("/api/v1/tasks").json() == []


def test_project_delete_not_found(client, admin_headers):
    response = client.delete("/api/v1/projects/9999", headers=admin_headers)
    assert response.status_code == 404


def test_columns_list_sorted(client):
    columns = client.get("/api/v1/columns").json()
    orders = [c["order"] for c in columns]
    assert orders == sorted(orders)
    assert len(columns) == 3


def test_columns_filter_by_project(client, admin_headers):
    client.post("/api/v1/projects", json={"title": "P2"}, headers=admin_headers)
    columns = client.get("/api/v1/columns?project_id=9999").json()
    assert columns == []
    columns = client.get("/api/v1/columns?project_id=1").json()
    assert len(columns) == 3


def test_column_create(client, admin_headers):
    response = client.post(
        "/api/v1/columns",
        json={"title": "Ревью", "wip_limit": 2, "project_id": 1},
        headers=admin_headers,
    )
    assert response.status_code == 201
    column = response.json()
    assert column["project_id"] == 1
    assert column["wip_limit"] == 2
    assert column["order"] > 3


def test_column_create_validation(client, admin_headers):
    assert (
        client.post("/api/v1/columns", json={}, headers=admin_headers).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/columns",
            json={"title": "x", "wip_limit": 0},
            headers=admin_headers,
        ).status_code
        == 422
    )


def test_column_create_unknown_project(client, admin_headers):
    response = client.post(
        "/api/v1/columns",
        json={"title": "x", "project_id": 9999},
        headers=admin_headers,
    )
    assert response.status_code == 404


def test_column_update(client, admin_headers, developer_headers):
    assert (
        client.put(
            "/api/v1/columns/1",
            json={"title": "Новое имя"},
            headers=developer_headers,
        ).status_code
        == 200
    )
    updated = client.get("/api/v1/columns").json()[0]
    assert updated["title"] == "Новое имя"
    assert client.put("/api/v1/columns/9999", json={"title": "x"}, headers=admin_headers).status_code == 404


def test_column_delete_rbac(client, admin_headers, manager_headers, developer_headers):
    assert (
        client.delete("/api/v1/columns/1", headers=developer_headers).status_code == 403
    )
    assert (
        client.delete("/api/v1/columns/1", headers=manager_headers).status_code == 200
    )
    assert client.delete("/api/v1/columns/9999", headers=admin_headers).status_code == 404


def test_column_delete_cascades_tasks(client, admin_headers):
    created = client.post(
        "/api/v1/columns",
        json={"title": "Temp", "wip_limit": 5, "project_id": 1},
        headers=admin_headers,
    )
    column_id = created.json()["id"]
    task = client.post(
        "/api/v1/tasks",
        json={"title": "Will be deleted", "column_id": column_id},
        headers=admin_headers,
    )
    assert task.status_code == 201
    client.delete(f"/api/v1/columns/{column_id}", headers=admin_headers)
    remaining = client.get("/api/v1/tasks").json()
    assert all(t["id"] != task.json()["id"] for t in remaining)


def test_task_list_seeded(client):
    tasks = client.get("/api/v1/tasks").json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Разработать REST API"


def test_task_filter_search(client, admin_headers):
    client.post(
        "/api/v1/tasks",
        json={"title": "Найти меня", "column_id": 1, "description": "особое слово"},
        headers=admin_headers,
    )
    assert len(client.get("/api/v1/tasks?search=яблоко").json()) == 0
    assert len(client.get("/api/v1/tasks?search=найт").json()) == 1
    assert len(client.get("/api/v1/tasks?search=особое").json()) == 1


def test_task_filter_assignee_case_insensitive_cyrillic(client, admin_headers):
    client.post(
        "/api/v1/tasks",
        json={"title": "T", "column_id": 1, "assignee": "Фёдор"},
        headers=admin_headers,
    )
    assert len(client.get("/api/v1/tasks?assignee=ФЁДОР").json()) == 1
    assert len(client.get("/api/v1/tasks?assignee=фёдор").json()) == 1
    assert len(client.get("/api/v1/tasks?assignee=unknown").json()) == 0


def test_task_filter_priority_tag_project(client, admin_headers):
    assert len(client.get("/api/v1/tasks?priority=high").json()) == 1
    assert len(client.get("/api/v1/tasks?priority=low").json()) == 0
    assert len(client.get("/api/v1/tasks?tag=backend").json()) == 1
    assert len(client.get("/api/v1/tasks?tag=mobile").json()) == 0
    assert len(client.get("/api/v1/tasks?project_id=1").json()) == 1
    assert len(client.get("/api/v1/tasks?project_id=42").json()) == 0


def test_task_create(client, admin_headers):
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": "Новая карточка",
            "column_id": 1,
            "project_id": 1,
            "description": "Описание",
            "assignee": "Валерия",
            "priority": "high",
            "deadline": "2026-12-01",
            "tags": "bug",
            "attachment_url": "https://example.com/file.png",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    task = response.json()
    assert task["id"] > 1
    assert task["assignee"] == "Валерия"


def test_task_create_defaults(client, admin_headers):
    response = client.post(
        "/api/v1/tasks",
        json={"title": "Минимум", "column_id": 1},
        headers=admin_headers,
    )
    assert response.status_code == 201
    task = response.json()
    assert task["assignee"] == "Не назначен"
    assert task["priority"] == "medium"
    assert task["project_id"] == 1
    assert task["deadline"] == ""


def test_task_create_validation(client, admin_headers):
    assert (
        client.post("/api/v1/tasks", json={}, headers=admin_headers).status_code == 422
    )
    assert (
        client.post(
            "/api/v1/tasks",
            json={"title": "   ", "column_id": 1},
            headers=admin_headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/tasks",
            json={"title": "x", "column_id": 1, "priority": "critical"},
            headers=admin_headers,
        ).status_code
        == 422
    )


def test_task_create_unknown_column_and_project(client, admin_headers):
    response = client.post(
        "/api/v1/tasks",
        json={"title": "x", "column_id": 9999},
        headers=admin_headers,
    )
    assert response.status_code == 404
    response = client.post(
        "/api/v1/tasks",
        json={"title": "x", "column_id": 1, "project_id": 9999},
        headers=admin_headers,
    )
    assert response.status_code == 404


def test_task_wip_limit_on_create(client, admin_headers):
    column = client.post(
        "/api/v1/columns",
        json={"title": "WIP", "wip_limit": 1, "project_id": 1},
        headers=admin_headers,
    ).json()
    first = client.post(
        "/api/v1/tasks",
        json={"title": "First", "column_id": column["id"]},
        headers=admin_headers,
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/tasks",
        json={"title": "Second", "column_id": column["id"]},
        headers=admin_headers,
    )
    assert second.status_code == 400
    assert "WIP" in second.json()["detail"]


def test_task_update_full_and_partial(client, admin_headers):
    task = client.post(
        "/api/v1/tasks",
        json={"title": "To update", "column_id": 1},
        headers=admin_headers,
    ).json()
    full = client.put(
        f"/api/v1/tasks/{task['id']}",
        json={
            "title": "Обновлено",
            "description": "Новое описание",
            "assignee": "Иван",
            "priority": "low",
            "deadline": "2027-01-01",
            "tags": "docs",
            "attachment_url": "https://example.com/a.png",
        },
        headers=admin_headers,
    )
    assert full.status_code == 200
    assert full.json()["title"] == "Обновлено"
    assert full.json()["priority"] == "low"

    partial = client.put(
        f"/api/v1/tasks/{task['id']}",
        json={"title": "Только имя"},
        headers=admin_headers,
    )
    assert partial.status_code == 200
    assert partial.json()["assignee"] == "Иван"
    assert partial.json()["priority"] == "low"

    assert (
        client.put(
            f"/api/v1/tasks/{task['id']}",
            json={"priority": "unknown"},
            headers=admin_headers,
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/v1/tasks/9999", json={"title": "x"}, headers=admin_headers
        ).status_code
        == 404
    )


def test_task_move(client, admin_headers):
    task = client.post(
        "/api/v1/tasks",
        json={"title": "Movable", "column_id": 1},
        headers=admin_headers,
    ).json()
    moved = client.put(
        f"/api/v1/tasks/{task['id']}/move?target_column_id=3",
        headers=admin_headers,
    )
    assert moved.status_code == 200
    assert moved.json()["column_id"] == 3

    again = client.put(
        f"/api/v1/tasks/{task['id']}/move?target_column_id=3",
        headers=admin_headers,
    )
    assert again.status_code == 200

    assert (
        client.put(
            f"/api/v1/tasks/{task['id']}/move?target_column_id=9999",
            headers=admin_headers,
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/api/v1/tasks/9999/move?target_column_id=1", headers=admin_headers
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/tasks/{task['id']}/move?target_column_id=1"
        ).status_code
        == 401
    )


def test_task_move_wip_limit(client, admin_headers):
    column = client.post(
        "/api/v1/columns",
        json={"title": "Solo", "wip_limit": 1, "project_id": 1},
        headers=admin_headers,
    ).json()
    client.post(
        "/api/v1/tasks",
        json={"title": "Occupier", "column_id": column["id"]},
        headers=admin_headers,
    )
    task = client.post(
        "/api/v1/tasks",
        json={"title": "Blocked", "column_id": 1},
        headers=admin_headers,
    ).json()
    response = client.put(
        f"/api/v1/tasks/{task['id']}/move?target_column_id={column['id']}",
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "WIP" in response.json()["detail"]


def test_task_delete(client, admin_headers):
    task = client.post(
        "/api/v1/tasks",
        json={"title": "Disposable", "column_id": 1},
        headers=admin_headers,
    ).json()
    assert (
        client.delete(f"/api/v1/tasks/{task['id']}", headers=admin_headers).status_code
        == 200
    )
    assert (
        client.delete(f"/api/v1/tasks/{task['id']}", headers=admin_headers).status_code
        == 404
    )


def test_task_history(client, admin_headers):
    seeded = client.get("/api/v1/tasks").json()[0]
    history = client.get(f"/api/v1/tasks/{seeded['id']}/history").json()
    assert history[0]["action"] == "Задача создана"

    client.put(
        f"/api/v1/tasks/{seeded['id']}/move?target_column_id=3",
        headers=admin_headers,
    )
    history = client.get(f"/api/v1/tasks/{seeded['id']}/history").json()
    assert len(history) == 2
    assert "Перемещена" in history[1]["action"]
    assert history[1]["timestamp"]

    assert client.get("/api/v1/tasks/9999/history").json() == []


def test_task_comments(client, admin_headers):
    task = client.post(
        "/api/v1/tasks",
        json={"title": "For comments", "column_id": 1},
        headers=admin_headers,
    ).json()
    assert client.get(f"/api/v1/tasks/{task['id']}/comments").json() == []

    created = client.post(
        f"/api/v1/tasks/{task['id']}/comments",
        json={"text": "Всё готово", "author": "admin"},
        headers=admin_headers,
    )
    assert created.status_code == 201
    assert created.json()["author"] == "admin"
    assert created.json()["timestamp"]

    comments = client.get(f"/api/v1/tasks/{task['id']}/comments").json()
    assert len(comments) == 1

    assert (
        client.post(
            "/api/v1/tasks/9999/comments",
            json={"text": "x", "author": "y"},
            headers=admin_headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/tasks/{task['id']}/comments",
            json={"text": "   ", "author": "y"},
            headers=admin_headers,
        ).status_code
        == 422
    )


def test_app_lifespan_runs_migrations_and_seed():
    with TestClient(app) as first_client:
        assert first_client.get("/api/v1/projects").status_code == 200
    with TestClient(app) as second_client:
        login = second_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin"}
        )
        assert login.status_code == 200


def test_column_create_without_any_project(client, admin_headers):
    client.delete("/api/v1/projects/1", headers=admin_headers)
    response = client.post("/api/v1/columns", json={"title": "x"}, headers=admin_headers)
    assert response.status_code == 404
