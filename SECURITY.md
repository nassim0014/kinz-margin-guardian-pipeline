# Security Policy

## Supported Versions

Only the latest `main` branch is supported with security updates.

## Reporting a Vulnerability

Email: nassim@kinzoils.com

Please include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You will receive a response within 48 hours.

## Security Measures

- API endpoints use JWT authentication with role-based access control (RBAC)
- Rate limiting via `slowapi` on API routes
- Password hashing with bcrypt (12 rounds)
- Audit logging on every mutation
- PostgreSQL with connection pooling
- Docker container isolation

## Dependencies

Dependencies are pinned where possible. The API requires
`fastapi httpx PyJWT slowapi` for the test suite to run in CI.
