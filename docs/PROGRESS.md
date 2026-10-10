# Progress

## Current milestone
Self-service password change and session invalidation.

## Verified recent work
- Automatic maintenance worker and all current migrations: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38019681845 (success).
- Schema changes through Alembic revision 0009_maint_gen_state pass PostgreSQL 16 upgrade and `alembic check`.

## Current change
Adds authenticated password change: verify current password, reject identical new password, set a new Argon2 hash, and revoke every active session. Tests cover invalid current password, unchanged password, successful change, refresh-token revocation, cross-session invalidation, and new login.

## Verification
Password-change tests and security chunk await CI. Password reset emails/account recovery remain separate work; no recovery link delivery is claimed.
