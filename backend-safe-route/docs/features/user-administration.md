# User administration

## Feature behavior

Authenticated administrators can list user accounts, update profile fields,
activate/deactivate accounts or change roles, set a user's local password, and
delete accounts. Responses include account identifiers and public profile,
status, role, and timestamps, but never password hashes. Ordinary users receive
HTTP 403 for administrative endpoints; unauthenticated users receive HTTP 401.

An administrator cannot demote or deactivate the last active administrator,
delete the last active administrator, or delete their own account. User
password changes are hashed before persistence and the endpoint returns no
password or hash.

## Edge cases

- Empty or null updates, and updates that include only one profile field.
- Unknown user IDs and invalid role or password values.
- User promotion/demotion, activation/deactivation, and the last-active-admin
  invariant.
- Deleting self, deleting a regular user, and deleting another administrator
  while a second active administrator remains.
- Updating a password and signing in with the new password; the old password
  must no longer work.
- Deactivating a user with a previously issued valid JWT; protected requests
  must reject it on the next request.
- Concurrent attempts to demote/delete separate administrators, database
  errors, and transaction rollback.

## Common user and system errors

- Non-admin access or absent/invalid bearer token.
- Attempt to delete self or remove the last active administrator.
- Invalid or missing update data and password shorter than policy.
- Unknown target user.
- Database errors during reads or mutations.

## Security considerations

- Re-authorize the current administrator from a verified JWT and current
  database state for every operation; do not trust role claims from client
  input or stale token data.
- Exclude password hashes and sensitive credentials from all response DTOs.
- Hash new passwords before persistence; never log submitted passwords.
- Preserve at least one active administrator, including when updates are
  concurrent.
- Use CSRF protections for cookie-authenticated admin-panel mutations and keep
  the administrative API bearer-authenticated.
- Return no database internals in error responses.

## Test scenarios

| Level | Scenario | Expected result |
|---|---|---|
| Unit | Admin dependency and update/password schemas | Non-admin is forbidden; malformed, empty, null, or too-short updates are rejected. |
| Integration | Promote/deactivate users, reset passwords, and delete users with seeded database state | Changes persist, passwords are hashed, and deletion cascades only as intended. |
| Integration | Demote/deactivate/delete the last active admin and delete self | Operations are rejected with conflict and database state remains unchanged. |
| E2E (API) | Admin JWT lists users, updates profile/role, and resets another user's password | API returns public fields only; new password works and old credential does not. |
| E2E (API) | Unauthenticated, ordinary-user, and deactivated-admin requests | Correct 401/403 responses; a deactivated admin's previously issued token is rejected. |
| Mixed | Database errors during mutation | Error is surfaced without leaking SQL details or leaving partial changes. |
| Security | Two administrators concurrently attempt removal of the last active admin | At least one active administrator remains after all operations settle. |
