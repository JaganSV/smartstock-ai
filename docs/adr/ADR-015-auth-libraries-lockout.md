# ADR-015: Authentication libraries and login lockout
Status: Accepted
Date: 2026-11-20 (accepted 2026-11-24)

## Context
BP §4.5 named passlib[bcrypt] for hashing and PyJWT or python-jose for tokens. BP §10.2 requires lockout after
5 failed logins in 15 minutes. The schema is frozen after P1 and `users` has no failed-attempt column.

## Options
A. passlib[bcrypt] + PyJWT, lockout counters in a new users column (schema change).
B. bcrypt directly + PyJWT, lockout derived from audit_log LOGIN_FAILED rows (no schema change).
C. python-jose instead of PyJWT.

## Decision
B. bcrypt directly (cost 12, 72-byte limit enforced, never truncated). PyJWT HS256, algorithms pinned to ["HS256"],
alg=none rejected. Lockout = LOGIN_FAILED audit rows for the lower-cased username within LOGIN_LOCK_MINUTES, newer
than the latest LOGIN_SUCCESS, >= LOGIN_MAX_FAILURES -> 429 RATE_LIMITED + Retry-After. Applies whether or not the
username exists.

## Consequences
+ No unmaintained dependency (passlib: no release since 2020, conflicts with current bcrypt). No schema change.
  Every lockout decision is backed by audit evidence.
- Lockout depends on the audit_log query (indexed on entity_type, entity_id).

## Affected artifacts
Blueprint §4.5, §10.2; BOB-P3-01; app/core/security.py; app/services/auth_service.py; app/repositories/audit.py;
tests/unit/test_security.py; tests/integration/test_auth.py.
