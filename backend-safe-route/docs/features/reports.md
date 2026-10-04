# Safety reports

## Feature behavior

Authenticated users can create and list their own safety reports, update or
delete only reports they own, list active nearby reports, and confirm eligible
reports submitted by other users. Nearby results include only reports whose
status is active, that have already been created, and whose expiry is absent or
in the future. Confirmation is idempotent per user/report pair; users cannot
confirm their own reports. Unauthorized ownership and ineligible reports are
concealed as not found.

## Edge cases

- Coordinates on the geographic bounds and values outside them.
- Empty or partial updates, especially a latitude without longitude.
- Nearby reports exactly at the radius boundary, outside the radius, expired,
  resolved, rejected, or created after the requested route time.
- A report with no expiry versus an expiry equal to the current time.
- The owner attempting to confirm their own report.
- Repeated confirmation by the same user and independent confirmation by a
  second user.
- Concurrent confirmations and deletion/update races.
- A report identifier that does not exist or belongs to another user.
- Database failure while selecting or mutating reports.

## Common user and system errors

- Invalid category, out-of-range coordinates, or incomplete update payload.
- Attempting to modify or delete another user's report.
- Confirming one's own, expired, or inactive report.
- Duplicate confirmation requests and transient transaction failures.

## Security considerations

- Derive the owner from the authenticated principal, never from client input.
- Scope reads and writes to the owner; return the same not-found response for
  missing and foreign-owned report identifiers.
- Keep nearby results limited to active, unexpired reports and bounded radii.
- Enforce uniqueness for confirmations in the database to handle retries and
  concurrent requests safely.
- Do not expose database exception text or internal user/report data.

## Test scenarios

| Level | Scenario | Expected result |
|---|---|---|
| Unit | Schema boundaries and empty/partial report updates | Valid boundaries pass; invalid or incomplete payloads fail validation. |
| Unit | Create, update, delete, list, and confirm service calls | Repository operations use the authenticated user ID and commit successful mutations only. |
| Integration | Seeded active, resolved, expired, future-created, and distant reports | Nearby PostGIS query returns only eligible reports within the requested radius. |
| Integration | Create/update/delete through repository and service | Geometry and ownership persist; foreign-owned changes do not affect the row. |
| Integration | Confirm another user's active report twice | Confirmation count increases once and exactly one unique confirmation is stored. |
| Integration | Self-confirm, expired report, and unknown ID | No confirmation is added; service/API returns the not-found behavior. |
| E2E (API) | Authenticated create/list/patch/delete lifecycle | Correct status and response DTOs; list is owner-scoped and no geometry internals leak. |
| Mixed | Report repository read raises a database exception | The error propagates; the service does not return a successful empty list or commit. |
| Security | Request without auth or with another user's ID | Authentication is required; client cannot choose the owner or access another user's mutation. |
