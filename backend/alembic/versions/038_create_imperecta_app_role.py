"""Create restricted application DB role imperecta_app (Level 2 seam 9.1).

Revision ID: 038_create_imperecta_app_role
Revises: 037_trim_dim_date_preseed
Create Date: 2026-06-28

Purpose: introduce the idle restricted login role for future gate-only writes.
The role is created with NO privileges, NO role memberships, and NO search_path
override. The application continues using the existing connection string until
seam 9.5 (switch) after SECURITY DEFINER functions and grants land in seams
9.2–9.3.

Operational note (non-secret): password is set out-of-band after deploy
(``ALTER ROLE imperecta_app PASSWORD ...``) and stored in Railway env for
seam 9.5; never committed to the repository.
"""

from alembic import op

revision = "038_create_imperecta_app_role"
down_revision = "037_trim_dim_date_preseed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: re-run is a no-op when the role already exists.
    # No PASSWORD clause — role stays inert under SCRAM until set out-of-band.
    # NOBYPASSRLS is the security crux (unlike postgres / service_role).
    # No GRANT, no membership, no ALTER ROLE ... SET search_path (seam 9.3).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'imperecta_app') THEN
                CREATE ROLE imperecta_app WITH
                    LOGIN
                    NOSUPERUSER
                    NOCREATEDB
                    NOCREATEROLE
                    NOINHERIT
                    NOREPLICATION
                    NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Assumes later seams (grants / app switch) are already downgraded.
    # At this revision the role owns no objects and holds no grants.
    op.execute("DROP ROLE IF EXISTS imperecta_app")
