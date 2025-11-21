"""add_flows_table

Revision ID: bafea4bca805
Revises: f6d01eea92e7
Create Date: 2025-11-21 12:14:43.947658

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = 'bafea4bca805'
down_revision: Union[str, None] = 'f6d01eea92e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create flows table
    op.create_table(
        "flows",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("nodes", JSON, nullable=False, server_default="[]"),
        sa.Column("edges", JSON, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(), nullable=False, server_default="'draft'"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("trigger_type", sa.String(), nullable=True),
        sa.Column("trigger_keywords", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_flows_id"), "flows", ["id"], unique=False)
    op.create_index(op.f("ix_flows_code"), "flows", ["code"], unique=True)


def downgrade() -> None:
    # Drop flows table
    op.drop_index(op.f("ix_flows_code"), table_name="flows")
    op.drop_index(op.f("ix_flows_id"), table_name="flows")
    op.drop_table("flows")
