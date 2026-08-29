"""Add tenant identity and row-level security.

Revision ID: 20260730_0002
Revises: 20260730_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260730_0002"
down_revision: str | None = "20260730_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

tenant_status = postgresql.ENUM(
    "ACTIVE", "SUSPENDED", name="tenant_status", create_type=False
)
role_name = postgresql.ENUM(
    "OWNER", "ADMIN", "OPERATOR", "VIEWER", name="role_name", create_type=False
)


def upgrade() -> None:
    tenant_status.create(op.get_bind(), checkfirst=True)
    role_name.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tenants",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("status", tenant_status, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("slug", name=op.f("uq_tenants_slug")),
    )
    op.create_table(
        "users",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", role_name, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_users_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint(
            "tenant_id",
            "email_normalized",
            name=op.f("uq_users_tenant_id"),
        ),
    )
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"])
    op.create_index("ix_users_tenant_active", "users", ["tenant_id", "is_active"])

    op.create_table(
        "refresh_sessions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_refresh_sessions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_sessions")),
        sa.UniqueConstraint(
            "token_hash",
            name=op.f("uq_refresh_sessions_token_hash"),
        ),
    )
    op.create_index(
        "ix_refresh_sessions_tenant_user",
        "refresh_sessions",
        ["tenant_id", "user_id"],
    )
    op.create_index(
        "ix_refresh_sessions_expires_at",
        "refresh_sessions",
        ["expires_at"],
    )

    for table in ("users", "refresh_sessions"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            """
        )


def downgrade() -> None:
    op.drop_table("refresh_sessions")
    op.drop_index("ix_users_tenant_active", table_name="users")
    op.drop_index(op.f("ix_users_tenant_id"), table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
    role_name.drop(op.get_bind(), checkfirst=True)
    tenant_status.drop(op.get_bind(), checkfirst=True)
