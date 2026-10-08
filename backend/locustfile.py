from locust import HttpUser, between, task


class KanbanUser(HttpUser):
    """Виртуальные пользователи Kanban-доски для нагрузочного тестирования.

    Каждый виртуальный пользователь авторизуется и работает в выделенной
    колонке с большим WIP-лимитом, чтобы 400-ошибки WIP не искажали
    результаты измерения времени отклика.
    """

    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.token = None
        self.column_id = None
        self.target_column_id = None
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        if response.status_code != 200:
            return
        self.token = response.json().get("access_token")
        self.column_id = self._ensure_column("Load Test Column")
        self.target_column_id = self._ensure_column("Load Test Target")

    def _ensure_column(self, title):
        columns = self.client.get("/api/v1/columns").json()
        existing = next((c for c in columns if c["title"] == title), None)
        if existing:
            return existing["id"]
        created = self.client.post(
            "/api/v1/columns",
            json={"title": title, "wip_limit": 1000},
            headers=self.auth_headers,
        )
        return created.json()["id"] if created.status_code == 201 else None

    @property
    def auth_headers(self):
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def list_tasks(self):
        self.client.get("/api/v1/tasks")

    @task(3)
    def list_columns(self):
        self.client.get("/api/v1/columns")

    @task(2)
    def search_tasks(self):
        self.client.get(
            "/api/v1/tasks",
            params={"search": "REST", "assignee": "валерия", "priority": "high"},
        )

    @task(1)
    def list_projects(self):
        self.client.get("/api/v1/projects")

    @task(1)
    def create_update_move_comment_delete(self):
        if not self.column_id or not self.target_column_id:
            return
        response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Load Test Task", "column_id": self.column_id},
            headers=self.auth_headers,
        )
        if response.status_code not in (200, 201):
            return
        task_id = response.json()["id"]
        self.client.put(
            f"/api/v1/tasks/{task_id}",
            json={"description": "Обновлено нагрузочным тестом", "priority": "high"},
            headers=self.auth_headers,
        )
        self.client.put(
            f"/api/v1/tasks/{task_id}/move",
            params={"target_column_id": self.target_column_id},
            headers=self.auth_headers,
        )
        self.client.post(
            f"/api/v1/tasks/{task_id}/comments",
            json={"text": "Нагрузочный комментарий", "author": "load-tester"},
            headers=self.auth_headers,
        )
        self.client.delete(f"/api/v1/tasks/{task_id}", headers=self.auth_headers)
