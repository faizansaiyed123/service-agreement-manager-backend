# Working state

- Active task: self-service password change.
- Current change updates auth route, password request schema, test coverage and checkpoint docs.
- API: POST /api/v1/auth/change-password; requires bearer access token plus current_password/new_password. New password minimum 12 characters. A successful change revokes all active sessions (including current), so caller must log in again.
- Tests cover invalid current password (401), same password (409), successful update (204), all access/refresh session invalidation, old-password login denial, new-password login success, and hash persistence.
- Next safe action: inspect CI, fix any exact failure, then implement email-based password recovery only if token/delivery flow can be completed safely.
