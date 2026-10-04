"""Spatial query API flows backed by the disposable local PostGIS database."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.mark.integration
@pytest.mark.e2e
def test_spatial_nearby_and_detail_endpoints_use_seeded_postgis(
    run_with_postgis_test_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario(sessions: async_sessionmaker) -> None:
        from geoalchemy2 import WKTElement

        from app.database.session import get_db
        from app.enums.crime_event import CrimeEventCategory
        from app.main import app
        from app.models.crime_event import CrimeEvent

        event_time = datetime.now(timezone.utc)
        lower_bound = event_time - timedelta(hours=1)
        upper_bound = event_time + timedelta(hours=1)
        async with sessions() as session:
            session.add_all(
                [
                    CrimeEvent(
                        category=CrimeEventCategory.ASSAULT,
                        geom=WKTElement("POINT(19.93605 50.0580)", srid=4326),
                        occurred_at=lower_bound,
                        source="e2e-lower-bound",
                    ),
                    CrimeEvent(
                        category=CrimeEventCategory.ROBBERY,
                        geom=WKTElement("POINT(19.9361 50.0580)", srid=4326),
                        occurred_at=upper_bound,
                        source="e2e-upper-bound",
                    ),
                ]
            )
            await session.commit()

        async def test_database_session():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_database_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                cases = (
                    ("/v1/safe-places", 19.9363, 50.0580),
                    ("/v1/crime-events", 19.9360, 50.0580),
                    ("/v1/cameras", 19.9362, 50.0580),
                    ("/v1/street-lamps", 19.9361, 50.0580),
                )
                for path, longitude, latitude in cases:
                    nearby_response = await client.get(
                        f"{path}/nearby",
                        params={
                            "lat": latitude,
                            "lon": longitude,
                            "radius_m": 1_000,
                        },
                    )
                    assert nearby_response.status_code == 200, nearby_response.text
                    nearby = nearby_response.json()
                    assert nearby
                    distances = [record["distance_m"] for record in nearby]
                    assert distances == sorted(distances)
                    assert all(distance <= 1_000 for distance in distances)
                    assert all(
                        "latitude" in record
                        and "longitude" in record
                        and "geom" not in record
                        for record in nearby
                    )

                    exact_match_response = await client.get(
                        f"{path}/nearby",
                        params={
                            "lat": latitude,
                            "lon": longitude,
                            "radius_m": 1,
                        },
                    )
                    assert exact_match_response.status_code == 200
                    exact_matches = exact_match_response.json()
                    assert len(exact_matches) == 1
                    assert exact_matches[0]["distance_m"] == pytest.approx(0)
                    detail_response = await client.get(
                        f"{path}/{exact_matches[0]['id']}"
                    )
                    assert detail_response.status_code == 200
                    detail = detail_response.json()
                    assert detail["latitude"] == pytest.approx(latitude)
                    assert detail["longitude"] == pytest.approx(longitude)
                    assert "distance_m" not in detail
                    assert "geom" not in detail

                    no_matches = await client.get(
                        f"{path}/nearby",
                        params={"lat": 0, "lon": 0, "radius_m": 1},
                    )
                    assert no_matches.status_code == 200
                    assert no_matches.json() == []

                    missing_detail = await client.get(f"{path}/2000000000")
                    assert missing_detail.status_code == 404

                crime_response = await client.get(
                    "/v1/crime-events/nearby",
                    params={
                        "lat": 50.0580,
                        "lon": 19.9360,
                        "radius_m": 100,
                        "occurred_after": lower_bound.isoformat(),
                        "occurred_before": upper_bound.isoformat(),
                    },
                )
                assert crime_response.status_code == 200, crime_response.text
                selected_events = crime_response.json()
                assert {event["source"] for event in selected_events} == {
                    "e2e-lower-bound",
                    "e2e-upper-bound",
                }
                assert [event["distance_m"] for event in selected_events] == sorted(
                    event["distance_m"] for event in selected_events
                )

                invalid_spatial_query = await client.get(
                    "/v1/cameras/nearby",
                    params={"lat": 91, "lon": 0},
                )
                invalid_radius = await client.get(
                    "/v1/safe-places/nearby",
                    params={"lat": 0, "lon": 0, "radius_m": 50_001},
                )
                invalid_event_time = await client.get(
                    "/v1/crime-events/nearby",
                    params={
                        "lat": 0,
                        "lon": 0,
                        "occurred_after": "not-a-timestamp",
                    },
                )
                assert invalid_spatial_query.status_code == 422
                assert invalid_radius.status_code == 422
                assert invalid_event_time.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db, None)

    run_with_postgis_test_database(scenario)


@pytest.mark.e2e
def test_spatial_endpoints_sanitize_database_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from fastapi.testclient import TestClient
    from sqlalchemy.exc import SQLAlchemyError

    from app.api.v1 import safe_places_router
    from app.database.session import get_db
    from app.main import app
    from app.services import camera_service, crime_event_service, street_lamp_service

    async def database_error(*args, **kwargs):
        raise SQLAlchemyError("private database detail")

    monkeypatch.setattr(
        safe_places_router,
        "_service",
        lambda session: SimpleNamespace(get_nearby=database_error),
    )
    monkeypatch.setattr(camera_service.CameraService, "get_nearby", database_error)
    monkeypatch.setattr(
        crime_event_service.CrimeEventService,
        "get_nearby",
        database_error,
    )
    monkeypatch.setattr(
        street_lamp_service.StreetLampService,
        "get_nearby",
        database_error,
    )
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            responses = [
                client.get(
                    f"{path}/nearby",
                    params={"lat": 50, "lon": 19},
                )
                for path in (
                    "/v1/safe-places",
                    "/v1/crime-events",
                    "/v1/cameras",
                    "/v1/street-lamps",
                )
            ]
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert [response.status_code for response in responses] == [500] * 4
    assert all("private database detail" not in response.text for response in responses)
