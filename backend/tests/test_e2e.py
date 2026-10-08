import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import expect

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def e2e_server(tmp_path_factory):
    """Живой uvicorn-сервер с отдельной временной БД для E2E-тестов."""
    port = _free_port()
    db_path = tmp_path_factory.mktemp("e2e") / "e2e.db"
    log_file = open(tmp_path_factory.mktemp("e2e") / "server.log", "w", encoding="utf8")
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["BCRYPT_ROUNDS"] = "4"
    env["SECRET_KEY"] = "e2e-secret-key-with-at-least-32-bytes-long"

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port),
            "--log-level", "warning",
        ],
        cwd=BACKEND_DIR,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        if proc.poll() is not None:
            log_file.flush()
            output = Path(log_file.name).read_text(errors="replace")
            raise RuntimeError(f"Сервер упал при старте:\n{output}")
        try:
            with urllib.request.urlopen(base_url + "/api/v1/projects", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.3)
    else:
        proc.terminate()
        raise RuntimeError("Сервер не поднялся за 60 секунд")

    yield base_url
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log_file.close()


@pytest.fixture
def dialogs(page):
    """Перехватывает все alert()/confirm() в виде списка сообщений."""
    messages: list[str] = []
    page.on("dialog", lambda dialog: (messages.append(dialog.message), dialog.accept()))
    return messages


def login(page, base_url, username="admin", password="admin"):
    page.goto(base_url)
    page.click("#btnLogin")
    page.fill("#loginUser", username)
    page.fill("#loginPass", password)
    page.click("#loginModal button:has-text('Войти')")
    return page.locator("#btnLogout")


def wait_for_dialog(page, dialogs, count=1, timeout=15.0):
    """Ждёт alert()/confirm(): событие доставляется только при вызовах Playwright API."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if len(dialogs) >= count:
            return dialogs
        page.evaluate("1")
        time.sleep(0.1)
    return dialogs


def test_board_renders_seeded_columns_and_task(e2e_server, page):
    page.goto(e2e_server)
    expect(page.locator("#board .column")).to_have_count(3)
    expect(page.get_by_text("Разработать REST API")).to_be_visible()
    expect(page.get_by_text("Бэклог")).to_be_visible()
    expect(page.locator(".wip-badge").first).to_contain_text("WIP")


def test_login_as_admin(e2e_server, page):
    logout_btn = login(page, e2e_server)
    expect(logout_btn).to_be_visible()
    expect(page.locator("#userStatus")).to_contain_text("admin")
    expect(page.locator("#userStatus")).to_contain_text("administrator")
    expect(page.locator("#btnLogin")).to_be_hidden()


def test_login_wrong_password_shows_alert(e2e_server, page, dialogs):
    page.goto(e2e_server)
    page.click("#btnLogin")
    page.fill("#loginUser", "admin")
    page.fill("#loginPass", "wrong-pass")
    page.click("#loginModal button:has-text('Войти')")
    wait_for_dialog(page, dialogs)
    expect(page.locator("#btnLogout")).to_be_hidden()
    assert any("Неверный логин или пароль" in m for m in dialogs), dialogs


def test_register_new_user_and_login(e2e_server, page, dialogs):
    page.goto(e2e_server)
    page.click("#btnReg")
    page.fill("#regUser", "e2e_dev")
    page.fill("#regPass", "pass123")
    page.click("#registerModal button:has-text('Зарегистрировать')")
    wait_for_dialog(page, dialogs)
    assert any("зарегистрирован" in m for m in dialogs), dialogs
    expect(page.locator("#registerModal")).to_be_hidden()

    page.click("#btnLogin")
    page.fill("#loginUser", "e2e_dev")
    page.fill("#loginPass", "pass123")
    page.click("#loginModal button:has-text('Войти')")
    expect(page.locator("#btnLogout")).to_be_visible()
    expect(page.locator("#userStatus")).to_contain_text("e2e_dev")
    expect(page.locator("#userStatus")).to_contain_text("developer")


def test_logout(e2e_server, page):
    login(page, e2e_server)
    page.click("#btnLogout")
    expect(page.locator("#btnLogin")).to_be_visible()
    expect(page.locator("#userStatus")).to_have_text("Статус: Гость")


def test_create_task_via_ui(e2e_server, page):
    login(page, e2e_server)
    page.click('[data-col-id="1"] button:has-text("Добавить задачу")')
    page.fill("#taskTitleInput", "E2E-задача из теста")
    page.fill("#taskAssigneeInput", "Валерия")
    page.select_option("#taskPrioritySelect", "high")
    page.click("#taskModal button:has-text('Создать')")
    expect(page.locator("#taskModal")).to_be_hidden()
    card = page.locator('[data-col-id="1"] .task-card', has_text="E2E-задача из теста")
    expect(card).to_be_visible()
    expect(card.locator(".priority")).to_have_text("high")


def test_create_column_via_ui(e2e_server, page):
    login(page, e2e_server)
    page.click('button:has-text("+ Колонка")')
    page.fill("#colTitleInput", "E2E-колонка")
    page.fill("#colWipInput", "4")
    page.click("#columnModal button:has-text('Сохранить')")
    expect(page.locator("#columnModal")).to_be_hidden()
    expect(page.locator("#board .column")).to_have_count(4)
    expect(page.get_by_text("E2E-колонка")).to_be_visible()


def test_drag_and_drop_moves_task(e2e_server, page):
    login(page, e2e_server)
    expect(page.locator('[data-col-id="2"] [data-task-id="1"]')).to_be_visible()
    page.drag_and_drop(
        '[data-col-id="2"] [data-task-id="1"]', '[data-col-id="3"]'
    )
    expect(page.locator('[data-col-id="3"] [data-task-id="1"]')).to_be_visible()


def test_search_filter_updates_board(e2e_server, page):
    page.goto(e2e_server)
    expect(page.locator(".task-card")).to_have_count(1)

    page.fill("#searchInput", "REST")
    expect(page.locator(".task-card")).to_have_count(1)
    expect(page.get_by_text("Разработать REST API")).to_be_visible()

    page.fill("#searchInput", "этого-не-существует")
    expect(page.locator(".task-card")).to_have_count(0)

    page.fill("#searchInput", "")
    expect(page.locator(".task-card")).to_have_count(1)


def test_assignee_filter_by_cyrillic(e2e_server, page):
    page.goto(e2e_server)
    page.fill("#filterAssignee", "валерия")
    expect(page.locator(".task-card")).to_have_count(1)
    page.fill("#filterAssignee", "несуществующий")
    expect(page.locator(".task-card")).to_have_count(0)


def test_task_details_history_and_comment(e2e_server, page):
    login(page, e2e_server)
    page.click('[data-col-id="2"] [data-task-id="1"]')
    expect(page.locator("#taskDetailsModal")).to_be_visible()
    expect(page.locator("#detTitleInput")).to_have_value("Разработать REST API")
    expect(page.locator("#detHistory")).to_contain_text("Задача создана")

    page.fill("#commentInput", "E2E-комментарий")
    page.click("#taskDetailsModal button:has-text('Отправить')")
    expect(page.locator("#detComments")).to_contain_text("E2E-комментарий")
    expect(page.locator("#detComments")).to_contain_text("admin")


def test_task_details_update(e2e_server, page):
    login(page, e2e_server)
    page.click('[data-col-id="2"] [data-task-id="1"]')
    expect(page.locator("#taskDetailsModal")).to_be_visible()
    page.fill("#detTitleInput", "Обновлено через E2E")
    page.select_option("#detPrioritySelect", "low")
    page.click("#taskDetailsModal button:has-text('Сохранить изменения')")
    expect(page.locator("#taskDetailsModal")).to_be_hidden()
    expect(page.locator(".task-card", has_text="Обновлено через E2E")).to_be_visible()


def test_xss_in_task_title_is_escaped(e2e_server, page, dialogs):
    xss_title = "<img src=x onerror=alert(1)>"
    login(page, e2e_server)
    page.click('[data-col-id="1"] button:has-text("Добавить задачу")')
    page.fill("#taskTitleInput", xss_title)
    page.click("#taskModal button:has-text('Создать')")
    card = page.locator(".task-card", has_text=xss_title)
    expect(card).to_be_visible()
    expect(card.locator(".task-title")).to_have_text(xss_title)
    assert card.locator("img").count() == 0
    page.wait_for_timeout(300)
    assert dialogs == [], dialogs
