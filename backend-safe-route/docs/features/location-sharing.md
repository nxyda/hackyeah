# Temporary location sharing

## Feature behavior

An authenticated owner can create one active share with an initial WGS84
location and duration from 1 second through 24 hours. Creation allocates a
unique four-digit code, serializing allocation in PostgreSQL and releasing codes
from expired or revoked shares. The owner can retrieve the active share, update
its latest location without changing its code or expiry, and revoke it. Another
authenticated user with the code can read the latest location but cannot write
to or revoke the share. The owner cannot read the share through the reader
endpoint. Expired or revoked shares are unavailable.

## Edge cases

- Coordinates at geographic limits and out-of-range values.
- Durations at 1 and 86,400 seconds, and values just outside that range.
- A share expiring during an update/read, or expiring at the exact current time.
- Owner already has an active share; owner has only expired/revoked shares.
- Existing codes, reuse after expiry/revocation, and all 10,000 codes occupied.
- Same-location update (must not write or commit); changed location update.
- Reader uses an unknown, malformed, expired, or revoked code.
- Owner tries to use their own code; another user guesses or reuses a code.
- Concurrent code allocation and database transaction failure.

## Common user and system errors

- Invalid coordinates, duration, or access-code format.
- Attempting to create a second active share for the same owner.
- Reading/updating/revoking a share that is missing, expired, or revoked.
- Exhausted code capacity or a database failure during allocation.

## Security considerations

- Require authentication for every endpoint and use the authenticated owner ID
  for owner operations.
- Share codes are bearer-like secrets with only 10,000 possible values; avoid
  logging them and rate-limit code reads at the deployment/API-gateway layer.
- Do not allow the owner to use the reader endpoint or expose write operations
  to readers.
- Expiry and revocation must immediately stop reads; revoked codes must not
  remain allocated.
- Validate coordinate bounds and share duration server-side.

## Test scenarios

| Level | Scenario | Expected result |
|---|---|---|
| Unit | Code allocation, duration, owner uniqueness, and code exhaustion | Four-digit unique code and bounded expiry; expected capacity/duplicate errors. |
| Unit | Same and changed location updates | Same location performs no update/commit; changed location preserves code and expiry. |
| Unit | Reader, owner, expiry, and revoke access rules | Only another user reads an active share; owner and stale codes are denied. |
| Integration | Seeded users and real PostGIS location rows | Create/read/update/revoke queries persist and return longitude/latitude in the correct order. |
| Integration | PostgreSQL advisory lock and expired/revoked code cleanup | Occupied active codes remain reserved while stale codes can be reused. |
| E2E (API) | Authenticated owner creates, reads, updates, and revokes; a second user reads | Correct HTTP contract, current coordinates, preserved expiry/code, and immediate revocation. |
| E2E (API) | Invalid payload, duplicate active share, and unknown code | Validation, conflict, and not-found responses are returned without leaking internals. |
| Mixed | Code-allocation lock fails with a database exception | Failure is propagated; no share is created or committed. |
| Security | Unauthenticated requests and owner-as-reader request | Authentication is required and owner cannot read through the public-code endpoint. |
