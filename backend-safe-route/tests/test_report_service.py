"""Testy kontraktów zgłoszeń oraz izolacji operacji per użytkownik."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.enums.report import ReportCategory, ReportStatus
from app.schemas.report import ReportCreate, ReportUpdate
from app.services.report_service import ReportService


class StubReportRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.session = SimpleNamespace(commit=self._commit)
        self.commits = 0
        self.report = SimpleNamespace(
            id=12,
            category=ReportCategory.DANGER,
            created_at=datetime.now(timezone.utc),
            expires_at=None,
            status=ReportStatus.ACTIVE,
            confirmations=0,
        )

    async def _commit(self) -> None:
        self.commits += 1

    async def list_for_user(self, user_id: int) -> list[tuple[object, float, float]]:
        self.calls.append(("list", {"user_id": user_id}))
        return [(self.report, 52.2, 21.0)]

    async def get_active_nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: float,
    ) -> list[tuple[object, float, float]]:
        self.calls.append(
            (
                "nearby",
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius_m": radius_m,
                },
            )
        )
        return [(self.report, 52.2, 21.0)]

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(("create", kwargs))
        return self.report

    async def get_by_id_for_user(
        self,
        report_id: int,
        user_id: int,
    ) -> tuple[object, float, float]:
        self.calls.append(("get", {"report_id": report_id, "user_id": user_id}))
        return self.report, 52.2, 21.0

    async def update_for_user(self, **kwargs: object) -> tuple[object, float, float]:
        self.calls.append(("update", kwargs))
        return self.report, 52.2, 21.0

    async def delete_for_user(self, report_id: int, user_id: int) -> bool:
        self.calls.append(("delete", {"report_id": report_id, "user_id": user_id}))
        return True

    async def confirm(
        self,
        report_id: int,
        user_id: int,
    ) -> tuple[SimpleNamespace, float, float]:
        self.calls.append(("confirm", {"report_id": report_id, "user_id": user_id}))
        self.report.confirmations += 1
        return self.report, 52.2, 21.0


def test_create_and_list_reports_use_authenticated_user_id() -> None:
    repository = StubReportRepository()
    service = ReportService(repository)
    request = ReportCreate(category=ReportCategory.DANGER, lat=52.2, lon=21.0)

    created = asyncio.run(service.create_report(7, request))
    reports = asyncio.run(service.list_reports(7))

    assert created.id == 12
    assert created.lat == 52.2
    assert created.lon == 21.0
    assert reports[0].category == ReportCategory.DANGER
    assert repository.calls[0] == (
        "create",
        {
            "user_id": 7,
            "category": ReportCategory.DANGER,
            "latitude": 52.2,
            "longitude": 21.0,
        },
    )
    assert repository.calls[2] == ("list", {"user_id": 7})
    assert repository.commits == 1


def test_update_and_delete_are_scoped_to_authenticated_user() -> None:
    repository = StubReportRepository()
    service = ReportService(repository)

    asyncio.run(service.update_report(9, 12, ReportUpdate(category=ReportCategory.OTHER)))
    asyncio.run(service.delete_report(9, 12))

    assert repository.calls[0] == (
        "update",
        {
            "report_id": 12,
            "user_id": 9,
            "category": ReportCategory.OTHER,
            "latitude": None,
            "longitude": None,
        },
    )
    assert repository.calls[1] == ("delete", {"report_id": 12, "user_id": 9})
    assert repository.commits == 2


def test_list_nearby_reports_passes_search_location_and_radius() -> None:
    repository = StubReportRepository()
    service = ReportService(repository)

    reports = asyncio.run(
        service.list_nearby_reports(
            latitude=52.2,
            longitude=21.0,
            radius_m=500,
        )
    )

    assert reports[0].id == 12
    assert reports[0].lat == 52.2
    assert reports[0].lon == 21.0
    assert repository.calls == [
        (
            "nearby",
            {"latitude": 52.2, "longitude": 21.0, "radius_m": 500},
        ),
    ]


def test_confirm_report_uses_authenticated_user_and_commits() -> None:
    repository = StubReportRepository()
    service = ReportService(repository)

    confirmed = asyncio.run(service.confirm_report(9, 12))

    assert confirmed is not None
    assert confirmed.id == 12
    assert confirmed.confirmations == 1
    assert repository.calls == [
        ("confirm", {"report_id": 12, "user_id": 9}),
    ]
    assert repository.commits == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"lat": 52.2},
        {"category": "danger", "lat": 52.2},
        {"category": "danger", "lat": 91, "lon": 21},
    ],
)
def test_report_update_rejects_invalid_location_or_empty_patch(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ReportUpdate.model_validate(payload)


def test_report_create_rejects_out_of_range_coordinates() -> None:
    with pytest.raises(ValidationError):
        ReportCreate(category=ReportCategory.DANGER, lat=52.2, lon=181)


def test_report_database_failure_is_propagated_without_a_success_shaped_result() -> None:
    repository = StubReportRepository()

    async def fail_list(user_id: int):
        raise SQLAlchemyError("report database unavailable")

    repository.list_for_user = fail_list

    with pytest.raises(SQLAlchemyError, match="report database unavailable"):
        asyncio.run(ReportService(repository).list_reports(7))

    assert repository.commits == 0
