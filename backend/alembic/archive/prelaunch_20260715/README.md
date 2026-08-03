# Pre-launch migration archive (2026-07-15)

This directory preserves the 98 migration files that formed the development
history before the first launch baseline. They are intentionally outside
`alembic/versions`, so Alembic does not load them into the active revision graph.

Do not run these revisions against a database created from the launch baseline.
They exist only for source archaeology and rollback-by-code-reference. Every
pre-launch development database must be rebuilt from the active baseline.

Configuration files and secret-bearing environment files were not moved or
rewritten as part of this archive.
