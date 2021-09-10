"""Create the users table

Revision ID: e6ae93737591
Revises:
Create Date: 2021-09-10 15:50:14.336770

"""
from alembic import op
import sqlalchemy as sa


revision = "e6ae93737591"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("login", sa.String(length=255), nullable=False),
        sa.Column("nfc_login", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_login"), "users", ["login"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_users_login"), table_name="users")
    op.drop_table("users")
