# Test environment

Tests must never connect to the application's configured database or to a
remote service. `tests/conftest.py` replaces application database settings
with dedicated local test values and blocks non-loopback socket connections
for every test. Mapbox tests use `httpx.MockTransport`; no test needs a Mapbox
token.

## Unit tests

Run the isolated test suite with:

```powershell
.\.venv\Scripts\python.exe -m pytest -m unit
```

The default pytest configuration measures app line coverage and lists missing
lines. To persist an HTML report, add `--cov-report=html` and inspect
`htmlcov/index.html`. Unit tests should mock external services and dependencies,
not use a database.

## Integration and API E2E tests

Spatial repositories use PostGIS-specific functions and cannot be integration
tested against SQLite. Start the disposable, local-only test database:

```powershell
docker compose -f docker-compose.test.yml up -d --wait
$env:SAFE_ROUTE_TEST_DATABASE_URL = "postgresql+asyncpg://safe_route_test:safe_route_test@127.0.0.1:55432/safe_route_test?ssl=disable"
.\.venv\Scripts\python.exe -m pytest -m "integration or e2e"
docker compose -f docker-compose.test.yml down
```

The integration fixture refuses any database URL except the dedicated
`safe_route_test` database on loopback port `55432`. Before each scenario it
drops and recreates the schema, enables PostGIS, and seeds deterministic users,
reports across active/resolved/expired and near/far cases, active and expired
location shares, and route/corridor data with alternative paths, multiple
crimes, lamps, cameras, and open/closed safe places. It drops the schema
afterward.
The fixture deliberately skips these tests when no explicit
`SAFE_ROUTE_TEST_DATABASE_URL` is set. Never point it at a developer, staging,
or production database.

## Test levels

- **Unit:** isolated schema, scoring, routing, and provider behavior.
- **Integration:** real local PostGIS repositories with external services
  mocked.
- **E2E (API):** the FastAPI route endpoint with seeded PostGIS and mocked
  Mapbox transport.
- **Mixed failures:** inject provider and repository failures at service/API
  boundaries; assert errors are surfaced rather than turned into successful
  empty results.

Feature behavior, edge cases, security considerations, and scenarios are
documented in [Route planning](features/route-planning.md),
[Safety reports](features/reports.md),
[Temporary location sharing](features/location-sharing.md),
[Authentication and registration](features/authentication.md),
[Nearby spatial data queries](features/spatial-data-queries.md), and
[User administration](features/user-administration.md).
