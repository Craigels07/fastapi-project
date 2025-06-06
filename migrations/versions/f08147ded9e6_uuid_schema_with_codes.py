"""uuid_schema_with_codes

Revision ID: f08147ded9e6
Revises:
Create Date: 2025-05-30 12:49:58.744960

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f08147ded9e6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_collections_id"), "collections", ["id"], unique=False)
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("filetype", sa.String(), nullable=True),
        sa.Column("filepath", sa.String(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_files_filename"), "files", ["filename"], unique=False)
    op.create_index(op.f("ix_files_id"), "files", ["id"], unique=False)
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("organization_metadata", sa.String(), nullable=True),
        sa.Column("woo_commerce", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_organizations_code"), "organizations", ["code"], unique=True
    )
    op.create_index(
        op.f("ix_organizations_email"), "organizations", ["email"], unique=True
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)
    op.create_index(
        op.f("ix_organizations_name"), "organizations", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_organizations_phone_number"),
        "organizations",
        ["phone_number"],
        unique=True,
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("preview", sa.String(), nullable=True),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("filepath", sa.String(), nullable=False),
        sa.Column("doc_metadata", sa.JSON(), nullable=True),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["collections.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_id"), "documents", ["id"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("password", sa.String(), nullable=False),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("user_metadata", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_code"), "users", ["code"], unique=True)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_name"), "users", ["name"], unique=False)
    op.create_index(
        op.f("ix_users_phone_number"), "users", ["phone_number"], unique=True
    )
    op.create_table(
        "whatsapp_users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("account_sid", sa.String(), nullable=True),
        sa.Column("phone_number", sa.String(), nullable=False),
        sa.Column("profile_name", sa.String(), nullable=True),
        sa.Column("user_metadata", sa.JSON(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number"),
    )
    op.create_index(
        op.f("ix_whatsapp_users_code"), "whatsapp_users", ["code"], unique=True
    )
    op.create_index(
        op.f("ix_whatsapp_users_id"), "whatsapp_users", ["id"], unique=False
    )
    op.create_table(
        "whatsapp_threads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("topic", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["whatsapp_users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_whatsapp_threads_code"), "whatsapp_threads", ["code"], unique=True
    )
    op.create_index(
        op.f("ix_whatsapp_threads_id"), "whatsapp_threads", ["id"], unique=False
    )
    op.create_table(
        "whatsapp_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("thread_id", sa.UUID(), nullable=True),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.String(), nullable=False),
        sa.Column("message_sid", sa.String(), nullable=True),
        sa.Column("wa_id", sa.String(), nullable=True),
        sa.Column("sms_status", sa.String(), nullable=True),
        sa.Column("profile_name", sa.String(), nullable=True),
        sa.Column("message_type", sa.String(), nullable=True),
        sa.Column("num_segments", sa.Integer(), nullable=True),
        sa.Column("num_media", sa.Integer(), nullable=True),
        sa.Column("media", sa.JSON(), nullable=True),
        sa.Column("message_metadata", sa.JSON(), nullable=True),
        sa.Column("intent", sa.String(), nullable=True),
        sa.Column("sentiment", sa.String(), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["whatsapp_threads.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["whatsapp_users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_whatsapp_messages_code"), "whatsapp_messages", ["code"], unique=True
    )
    op.create_index(
        op.f("ix_whatsapp_messages_id"), "whatsapp_messages", ["id"], unique=False
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_whatsapp_messages_id"), table_name="whatsapp_messages")
    op.drop_index(op.f("ix_whatsapp_messages_code"), table_name="whatsapp_messages")
    op.drop_table("whatsapp_messages")
    op.drop_index(op.f("ix_whatsapp_threads_id"), table_name="whatsapp_threads")
    op.drop_index(op.f("ix_whatsapp_threads_code"), table_name="whatsapp_threads")
    op.drop_table("whatsapp_threads")
    op.drop_index(op.f("ix_whatsapp_users_id"), table_name="whatsapp_users")
    op.drop_index(op.f("ix_whatsapp_users_code"), table_name="whatsapp_users")
    op.drop_table("whatsapp_users")
    op.drop_index(op.f("ix_users_phone_number"), table_name="users")
    op.drop_index(op.f("ix_users_name"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_code"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_documents_id"), table_name="documents")
    op.drop_table("documents")
    op.drop_index(op.f("ix_organizations_phone_number"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_id"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_email"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_code"), table_name="organizations")
    op.drop_table("organizations")
    op.drop_index(op.f("ix_files_id"), table_name="files")
    op.drop_index(op.f("ix_files_filename"), table_name="files")
    op.drop_table("files")
    op.drop_index(op.f("ix_collections_id"), table_name="collections")
    op.drop_table("collections")
    # ### end Alembic commands ###
