# Authentication and registration

## Feature behavior

Local registration accepts an email, a password of 12 to 1024 characters, and
optional names. Email addresses are normalized to lowercase and whitespace is
trimmed. Passwords are hashed before persistence. Successful registration
returns a short-lived JWT and a public profile; duplicate email addresses return
HTTP 409.

Local login verifies the submitted password against the stored password hash and
returns a short-lived JWT only for an active account. Unknown accounts, invalid
passwords, and inactive accounts share the same HTTP 401 response. Tokens are
signed by the server, include an issuer and expiry, and are checked against the
current account on protected endpoints.

Google and Facebook login verify credentials with the configured provider,
then either issue a token for an existing linked active identity or create a
new account and identity. Provider identities are matched by provider and
provider subject, not by email. An existing local account with the same email
is not automatically linked. Provider-verification failures are translated to
sanitized authentication errors.

## Edge cases

- Emails with uppercase letters or surrounding whitespace, invalid email
  syntax, and duplicate emails submitted concurrently.
- Passwords at the minimum and maximum accepted lengths, and passwords with
  incorrect values or unsupported length.
- Unknown user, missing password hash (OAuth-only account), incorrect password,
  and inactive local account.
- JWT with malformed encoding, bad signature, wrong issuer, missing claims,
  expired/not-yet-valid timestamps, non-numeric or non-positive subject, and a
  user deleted or deactivated after token issuance.
- OAuth credential rejected, provider timeout/5xx, malformed provider response,
  unverified Google email, expired or wrong-app Facebook token, and profile
  subject mismatch.
- OAuth login for a linked account, concurrent first login for the same
  identity, and an identity/email already associated with another account.
- Database failure during registration, identity creation, commit, or rollback.

## Common user and system errors

- Invalid email or a password shorter than the registration minimum.
- Duplicate registration or attempting OAuth with an email already registered
  through another method.
- Incorrect credentials or use of a deactivated account.
- Missing/invalid JWT, expired access token, or a token for a deactivated user.
- Missing server-side JWT/OAuth configuration or an unavailable OAuth provider.
- Persistence conflicts during concurrent account or identity creation.

## Security considerations

- Store only password hashes and never include submitted passwords, raw OAuth
  credentials, access tokens, or provider secrets in logs or responses.
- Return indistinguishable login failures for unknown users, bad passwords, and
  inactive users; perform dummy password verification for unknown/OAuth-only
  accounts to reduce timing-based account enumeration.
- Validate provider signatures, audience/app ownership, expiry, subject, and
  email verification before accepting OAuth claims. Never trust profile data
  supplied directly by the client.
- Do not automatically link an OAuth identity to a local account solely because
  its email matches.
- Sign JWTs with a sufficiently strong configured secret; validate signature,
  algorithm, issuer, time claims, and positive user subject, then re-check that
  the account remains active.
- Translate provider, JWT configuration, and persistence failures into
  sanitized API responses. Tests must use a dedicated local database and must
  not make requests to real identity providers.

## Test scenarios

| Level | Scenario | Expected result |
|---|---|---|
| Unit | Register with mixed-case/space-padded email and names | Email and names are normalized, password is hashed, and only public profile fields are returned. |
| Unit | Register an existing email or race on the unique email constraint | Duplicate account error is surfaced; failed transaction is rolled back. |
| Unit | Login for valid, unknown, bad-password, OAuth-only, and inactive accounts | Only an active account with a valid password receives a correctly signed short-lived JWT; all invalid credentials fail uniformly. |
| Unit | Decode malformed, expired, wrong-issuer, invalid-subject, and bad-signature tokens | Authentication rejects every invalid token without exposing token details. |
| Unit | Verify Google/Facebook identity and malformed, rejected, expired, or unavailable provider responses | Only validated provider claims produce a profile; provider errors map to typed failures. |
| Unit | OAuth identity reuse, email collision, and concurrent first-login race | Linked identity signs in; email-only linking is rejected; a concurrent valid identity resolves to one account. |
| Integration | Register, persist, and log in against the dedicated local database | Password hash and user persist; token identifies the normalized account and has configured expiry. |
| Integration | Duplicate registration and transaction failure | No duplicate account is created; failed writes are rolled back. |
| E2E (API) | Register, log in, and call a protected endpoint with the resulting JWT | HTTP contracts, response model, bearer authorization, and current-account lookup work end to end. |
| E2E (API) | Invalid credentials, malformed input, and invalid/expired JWT | Sanitized 4xx responses are returned and protected data remains inaccessible. |
| Mixed | OAuth HTTP timeout/provider error and database commit failure | Requests use mocked provider responses; failures are surfaced without leaking secrets or creating partial identities. |
| Security | Run auth tests with external network disabled | No Google/Facebook or other non-loopback request can leave the test process. |
