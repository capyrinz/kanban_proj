import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import load_secret_key, settings
from app.schemas.kanban import ColumnCreate, ColumnUpdate, TaskCreate, TaskUpdate, UserRegister
from app.services import auth as auth_service
from app.services import board as board_service
from app.services import projects as project_service


def test_column_create_defaults():
    column = ColumnCreate(title="QA")
    assert column.wip_limit == 3
    assert column.order is None
    assert column.project_id is None


def test_column_create_rejects_empty_title():
    with pytest.raises(ValidationError):
        ColumnCreate(title="   ")


def test_column_create_rejects_zero_wip():
    with pytest.raises(ValidationError):
        ColumnCreate(title="QA", wip_limit=0)


def test_column_update_all_fields_optional():
    update = ColumnUpdate()
    assert update.title is None
    assert update.wip_limit is None
    assert update.order is None


def test_task_create_priority_literal():
    with pytest.raises(ValidationError):
        TaskCreate(title="Task", column_id=1, priority="urgent")
    task = TaskCreate(title="Task", column_id=1, priority="high")
    assert task.priority == "high"


def test_task_create_strips_title():
    task = TaskCreate(title="  My Task  ", column_id=1)
    assert task.title == "My Task"


def test_task_update_partial():
    update = TaskUpdate(title="Only title")
    assert update.title == "Only title"
    assert update.description is None
    assert update.priority is None


def test_user_register_requires_password():
    with pytest.raises(ValidationError):
        UserRegister(username="user1", password="")


def test_hash_and_verify_password():
    hashed = auth_service.hash_password("qwerty")
    assert hashed != "qwerty"
    assert auth_service.verify_password("qwerty", hashed) is True
    assert auth_service.verify_password("other", hashed) is False


def test_verify_password_handles_invalid_hash():
    assert auth_service.verify_password("qwerty", "not-a-hash") is False


def test_access_token_roundtrip():
    token = auth_service.create_access_token("admin", "administrator")
    payload = auth_service.decode_token(token)
    assert payload is not None
    assert payload["sub"] == "admin"
    assert payload["role"] == "administrator"
    assert "exp" in payload


def test_decode_token_rejects_garbage():
    assert auth_service.decode_token("not.a.jwt") is None


def test_decode_token_rejects_wrong_secret(monkeypatch):
    token = auth_service.create_access_token("admin", "administrator")
    monkeypatch.setattr(settings, "secret_key", "another-secret-with-more-than-32-bytes-length")
    assert auth_service.decode_token(token) is None


def test_load_secret_key_from_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "explicit-key")
    assert load_secret_key() == "explicit-key"


def test_load_secret_key_generated_when_unset(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    assert len(load_secret_key()) > 32


async def test_register_and_authenticate(db_session):
    user = await auth_service.register_user(db_session, "alice", "pass1", "developer")
    assert user.username == "alice"
    assert user.role == "developer"
    assert user.hashed_password != "pass1"
    logged = await auth_service.authenticate(db_session, "alice", "pass1")
    assert logged.id == user.id


async def test_register_rejects_administrator_role(db_session):
    with pytest.raises(HTTPException) as exc:
        await auth_service.register_user(db_session, "root", "pass1", "administrator")
    assert exc.value.status_code == 403


async def test_register_rejects_unknown_role(db_session):
    with pytest.raises(HTTPException) as exc:
        await auth_service.register_user(db_session, "root", "pass1", "superuser")
    assert exc.value.status_code == 403


async def test_register_duplicate_username(db_session):
    await auth_service.register_user(db_session, "alice", "pass1", "developer")
    with pytest.raises(HTTPException) as exc:
        await auth_service.register_user(db_session, "alice", "pass2", "developer")
    assert exc.value.status_code == 409


async def test_authenticate_unknown_user(db_session):
    with pytest.raises(HTTPException) as exc:
        await auth_service.authenticate(db_session, "ghost", "pass1")
    assert exc.value.status_code == 401


async def test_authenticate_wrong_password(db_session):
    await auth_service.register_user(db_session, "alice", "pass1", "developer")
    with pytest.raises(HTTPException) as exc:
        await auth_service.authenticate(db_session, "alice", "wrong")
    assert exc.value.status_code == 401


async def test_project_service_crud(db_session):
    project = await project_service.create_project(db_session, "Новый", "Описание")
    updated = await project_service.update_project(
        db_session, project.id, None, "Другое описание"
    )
    assert updated.title == "Новый"
    assert updated.description == "Другое описание"
    updated = await project_service.update_project(db_session, project.id, "Имя", None)
    assert updated.title == "Имя"
    await project_service.delete_project(db_session, project.id)
    with pytest.raises(HTTPException):
        await project_service.get_project_or_404(db_session, project.id)


async def test_column_service_order_assignment(db_session):
    first = await board_service.create_column(
        db_session, ColumnCreate(title="First", wip_limit=4)
    )
    second = await board_service.create_column(db_session, ColumnCreate(title="Second"))
    assert first.project_id == 1
    assert first.wip_limit == 4
    assert second.order > first.order


async def test_column_service_update_and_delete(db_session):
    column = await board_service.create_column(db_session, ColumnCreate(title="Temp"))
    updated = await board_service.update_column(
        db_session, column.id, ColumnUpdate(title="Renamed", wip_limit=7, order=99)
    )
    assert updated.title == "Renamed"
    assert updated.wip_limit == 7
    assert updated.order == 99
    updated = await board_service.update_column(
        db_session, column.id, ColumnUpdate(wip_limit=8)
    )
    assert updated.title == "Renamed"
    assert updated.wip_limit == 8
    await board_service.delete_column(db_session, column.id)
    with pytest.raises(HTTPException):
        await board_service.get_column_or_404(db_session, column.id)


async def test_column_service_unknown_project(db_session):
    with pytest.raises(HTTPException) as exc:
        await board_service.create_column(
            db_session, ColumnCreate(title="X", project_id=999)
        )
    assert exc.value.status_code == 404


async def test_task_service_full_flow(db_session):
    task = await board_service.create_task(
        db_session,
        TaskCreate(title="Новая задача", column_id=1, assignee="Иван", priority="high"),
    )
    assert task.assignee == "Иван"
    history = await board_service.task_history(db_session, task.id)
    assert [e.action for e in history] == ["Задача создана"]

    updated = await board_service.update_task(
        db_session, task.id, TaskUpdate(description="Описание", tags="bug")
    )
    assert updated.description == "Описание"

    moved = await board_service.move_task(db_session, task.id, 3)
    assert moved.column_id == 3
    history = await board_service.task_history(db_session, task.id)
    assert "Перемещена" in history[-1].action

    same = await board_service.move_task(db_session, task.id, 3)
    assert same.column_id == 3

    await board_service.delete_task(db_session, task.id)
    with pytest.raises(HTTPException):
        await board_service.get_task_or_404(db_session, task.id)


async def test_task_service_wip_limit(db_session):
    await board_service.create_column(
        db_session, ColumnCreate(title="WIP col", wip_limit=1, project_id=1)
    )
    columns = await board_service.list_columns(db_session, 1)
    target = next(c for c in columns if c.title == "WIP col")
    await board_service.create_task(
        db_session, TaskCreate(title="One", column_id=target.id)
    )
    with pytest.raises(HTTPException) as exc:
        await board_service.create_task(
            db_session, TaskCreate(title="Two", column_id=target.id)
        )
    assert exc.value.status_code == 400


async def test_task_service_not_found(db_session):
    with pytest.raises(HTTPException) as exc:
        await board_service.move_task(db_session, 9999, 1)
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        await board_service.move_task(db_session, 1, 9999)
    assert exc.value.status_code == 404


async def test_task_service_unknown_column(db_session):
    with pytest.raises(HTTPException) as exc:
        await board_service.create_task(
            db_session, TaskCreate(title="X", column_id=9999)
        )
    assert exc.value.status_code == 404


async def test_task_service_unknown_project(db_session):
    with pytest.raises(HTTPException) as exc:
        await board_service.create_task(
            db_session, TaskCreate(title="X", column_id=1, project_id=9999)
        )
    assert exc.value.status_code == 404


async def test_task_service_defaults(db_session):
    task = await board_service.create_task(
        db_session, TaskCreate(title="Без опций", column_id=1)
    )
    assert task.assignee == "Не назначен"
    assert task.priority == "medium"
    assert task.deadline == ""
    assert task.tags == ""
    assert task.attachment_url == ""
    assert task.project_id == 1


async def test_comment_service(db_session):
    task = await board_service.create_task(
        db_session, TaskCreate(title="For comment", column_id=1)
    )
    comment = await board_service.add_comment(db_session, task.id, "Валерия", "Привет")
    assert comment.author == "Валерия"
    comments = await board_service.task_comments(db_session, task.id)
    assert len(comments) == 1

    with pytest.raises(HTTPException) as exc:
        await board_service.add_comment(db_session, 9999, "x", "y")
    assert exc.value.status_code == 404


async def test_task_filters(db_session):
    await board_service.create_task(
        db_session,
        TaskCreate(
            title="Filter target",
            column_id=1,
            assignee="Фёдор",
            priority="low",
            tags="frontend, ui",
            description="уникальное слово xyzt",
        ),
    )
    found = await board_service.list_tasks(db_session, 1, "xyzt", None, None, None)
    assert len(found) == 1
    found = await board_service.list_tasks(db_session, 1, None, "фёдор", None, None)
    assert len(found) == 1
    found = await board_service.list_tasks(db_session, 1, None, None, "low", None)
    assert len(found) == 1
    found = await board_service.list_tasks(db_session, 1, None, None, None, "UI")
    assert len(found) == 1
    found = await board_service.list_tasks(db_session, 999, None, None, None, None)
    assert found == []


async def test_history_of_unknown_task(db_session):
    assert await board_service.task_history(db_session, 9999) == []
    assert await board_service.task_comments(db_session, 9999) == []
