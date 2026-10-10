# Working state

- Active task: renewal offer persistence.
- Current commit adds AgreementRenewal, migration 0006, exports it from app.models, and updates recovery checkpoints.
- Next feature commit adds tenant-scoped offer/create/list/accept/decline APIs and tests.
- Acceptance criteria: offer snapshots terms/prices; only authorized company staff can create/manage it; proposed term follows source agreement's end; accept creates a successor agreement using frozen offer prices and acceptance evidence; duplicate or expired acceptance is rejected; decline records reason; source and successor history remains intact.
- PostgreSQL execution of migrations 0001–0006 remains to be run in a real PostgreSQL environment; CI SQLite tests alone do not verify migration compatibility.
