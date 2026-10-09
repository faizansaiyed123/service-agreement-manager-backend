# Working state

- Active task: Verify the initial backend slice and correct defects.
- Acceptance: imports succeed; migration builds current identity/CRM tables; health endpoints respond; registration/login/refresh works; customer/contact/location APIs enforce tenant scope; tests and Ruff pass.
- Latest source commit: 83830f5a5c45a9bcd36407f8ad370114b1a46923.
- Migration: 0001_initial; PostgreSQL execution not yet verified.
- Tests: files committed, CI result pending.
- Local changes: no connected local working tree; edits are sent through GitHub Git database APIs.
- Next safe action: add API tests/CI/docs commit; inspect workflow; fix observed failures before extending domain scope.
