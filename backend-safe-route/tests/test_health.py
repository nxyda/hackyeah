"""Test działającego endpointu health."""

import logging

import pytest

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    """Endpoint health zwraca poprawny status i metadane."""

    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.1.0"


def test_requests_are_logged_with_request_id_without_logging_query_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="app.main"):
        response = TestClient(app).get("/health?access_token=must-not-be-logged")

    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    assert request_id
    assert "HTTP request" in caplog.text
    assert "route=/health" in caplog.text
    assert f"request_id={request_id}" in caplog.text
    assert "must-not-be-logged" not in caplog.text
