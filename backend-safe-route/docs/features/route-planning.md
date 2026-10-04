# Route planning

## Feature behavior

`POST /v1/route` accepts start and destination coordinates, a timezone-aware
departure time, a safety weight from 0 to 1, and the `walking` profile. The
route service requests walking routes and alternatives from Mapbox Directions,
then loads road segments and nearby crime events, street lamps, cameras, safe
places, and active reports from the database. It builds local route candidates,
scores all candidates for travel time and safety, and returns the fastest and
safest options, any remaining alternatives, and data-coverage metadata.

If no usable route is returned, the service reports that routing is
unavailable. The HTTP endpoint returns `400` for rejected route input and
`503` when the route provider is unavailable. When there are no local road
segments, Mapbox routes remain usable and the response reports `mapbox_only`
coverage.

## Edge cases

- Coordinates at the valid geographic limits and values just outside them.
- Identical start and destination, invalid coordinate pairs, and malformed JSON.
- Missing or timezone-naive departure time; safety weights below 0 or above 1.
- No Mapbox routes, malformed provider payloads, or only one route alternative.
- Empty corridor data and partially populated safety data.
- Reports that are expired, resolved, or created after the requested departure.
- Safe places that are closed at the requested departure time.
- Equal-duration or equal-safety candidates and duplicate route geometries.
- Database failures while reading any corridor data.

## Common user and system errors

- Reversed latitude/longitude values or coordinates outside geographic bounds.
- Invalid or absent departure time and safety weight outside `[0, 1]`.
- Mapbox timeouts, HTTP errors, malformed JSON, or unusable geometry/metrics.
- Empty or stale spatial datasets, unavailable PostGIS, and query failures.
- Missing optional safety attributes, which must not make otherwise valid routes
  unusable.

## Security considerations

- Never expose the Mapbox access token or provider response details in client
  errors or logs.
- Validate coordinates and bounded scoring inputs before external calls.
- Keep Mapbox requests server-side; tests must use a mock transport and must not
  send requests to Mapbox.
- Use parameterized database queries and constrain spatial queries to the
  requested corridor and configured buffer.
- Do not allow test setup or cleanup to connect to or mutate a non-test database.
- Avoid logging precise user start/end coordinates or other sensitive location
  data.

## Test scenarios

| Level | Scenario | Expected result |
|---|---|---|
| Unit | Valid Mapbox route payload and alternatives | Routes map to validated route models; outbound request uses the walking endpoint. |
| Unit | Geographic coordinate limits and values outside the limits | Boundary coordinates are accepted; out-of-range latitude/longitude is rejected. |
| Unit | Malformed payload, HTTP error, transport failure | A typed provider error is raised without leaking provider details. |
| Unit | Scoring with missing optional safety attributes | Scores and response models remain valid. |
| Integration | Route request with seeded PostGIS corridor and a mocked Mapbox response | Database repositories, local routing/scoring, and response serialization work together. |
| Integration | Empty corridor or no usable provider route | Mapbox-only coverage is returned or routing fails explicitly. |
| Integration | Repository query raises a database error | Failure is visible and is not represented as a successful empty result. |
| E2E (API) | `POST /v1/route` with valid request and test dependencies | HTTP 200 response contains fastest, safest, alternatives, and metadata. |
| E2E (API) | Invalid request and empty route-provider result | HTTP 422 is returned before calling the provider; provider outage returns sanitized HTTP 503. |
| Security | Entire test suite attempts external HTTP access | Non-loopback network connections are blocked; Mapbox calls use mock transports only. |
