"""Prueba de carga CP-01 - Dashboard S.A.P.I."""

from __future__ import annotations

from locust import HttpUser, between, task


class DashboardUser(HttpUser):
    """Simula analistas concurrentes consultando el dashboard."""

    wait_time = between(1, 3)

    @task(3)
    def load_dashboard(self) -> None:
        self.client.get("/")

    @task(1)
    def health(self) -> None:
        self.client.get("/_stcore/health")
