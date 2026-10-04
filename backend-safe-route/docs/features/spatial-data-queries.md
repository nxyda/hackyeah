# Nearby spatial data queries

## Feature behavior

The read-only API exposes detail and nearby-search endpoints for safe places,
historical crime events, cameras, and street lamps. Nearby searches accept a
WGS84 latitude/longitude point and a radius greater than zero and no greater
than 50 km. Safe-place searches default to 1 km; the other search endpoints
also default to 1 km. Results are limited by PostGIS distance and ordered
nearest-first. Responses include public attributes, WGS84 coordinates, and
distance in metres; detail responses omit the distance. Crime-event searches
add optional inclusive `occurred_after` and `occurred_before` filters.

Detail requests return the corresponding public DTO or HTTP 404. Nearby
requests return an empty list when no records match. Invalid coordinates,
radius values, and malformed query parameters are rejected by request
validation. Database errors return a generic HTTP 500 response rather than
internal SQL or database details.

## Edge cases

- Latitude at -90/90 and longitude at -180/180, as well as values just outside
  those limits.
- Radius at the maximum, zero/negative radius, and a result exactly at or just
  outside the requested radius.
- Search point equals a record location (zero distance), equal-distance ties,
  empty datasets, and no matching records.
- Longitude/latitude axis order in PostGIS point creation and serialized DTOs.
- Crime events exactly at `occurred_after` or `occurred_before`, reversed date
  bounds, timezone offsets, and malformed timestamps.
- Missing detail identifiers and database read failures.
- Records near coordinate-system edges or invalid geometry in imported data.

## Common user and system errors

- Latitude/longitude swapped or outside WGS84 limits.
- Radius omitted (default applies), set to zero, negative, or greater than
  50 km.
- Invalid date strings or date windows containing no events.
- Requesting an unknown database identifier.
- PostGIS outage, query timeout, or corrupt imported geometry.

## Security considerations

- Use bound SQL parameters and PostGIS spatial predicates; never interpolate
  user input into SQL or WKT.
- Bound query radius and validate coordinate ranges to prevent unbounded
  spatial scans or malformed spatial queries.
- Return only response DTO fields; never serialize database geometry,
  connection data, or SQL exception text.
- Validate identifier and timestamp input at the HTTP boundary.
- Keep tests on the dedicated local PostGIS database and block non-loopback
  networking; these endpoints must not call external map or geocoding APIs.

## Test scenarios

| Level | Scenario | Expected result |
|---|---|---|
| Unit | Query input boundary and detail DTO mapping | Geographic/radius boundaries validate correctly; DTOs expose coordinates and public fields only. |
| Integration | Seeded PostGIS nearby query for each spatial entity | Only in-radius rows are returned in ascending distance order, with correctly ordered latitude/longitude and metre distances. |
| Integration | Query exactly at a seeded entity with a 1 m radius | The matching entity is returned at approximately zero distance; other nearby entities are excluded. |
| Integration | Crime-event date window with records on both sides and at its inclusive boundaries | Only events inside the inclusive date and spatial filters are returned. |
| Integration | Unknown detail identifier and no nearby matches | Detail endpoints return not found; nearby endpoints return an empty list. |
| E2E (API) | Nearby and detail requests for safe places, crime events, cameras, and street lamps | HTTP status, response shape, ordering, coordinate axes, and actual PostGIS results match the contract. |
| E2E (API) | Out-of-range coordinates, invalid radius, and malformed event timestamps | Request is rejected before any spatial query can run. |
| Mixed | Repository/query failure | API returns a generic server error without leaking the database exception. |
| Security | Execute all spatial endpoint tests with external network disabled | Tests use only seeded local PostGIS and make no external service calls. |
