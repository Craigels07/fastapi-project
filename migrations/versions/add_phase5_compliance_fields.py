"""Add Phase 5 compliance fields

Revision ID: a1b2c3d4e5f6
Revises: 789aa8f4f68f
Create Date: 2026-01-01 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '789aa8f4f68f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add messaging_service_sid to whatsapp_accounts
    op.add_column('whatsapp_accounts', sa.Column('messaging_service_sid', sa.String(), nullable=True))
    op.create_index(op.f('ix_whatsapp_accounts_messaging_service_sid'), 'whatsapp_accounts', ['messaging_service_sid'], unique=False)
    
    # Add waba_verification_status to whatsapp_accounts
    op.add_column('whatsapp_accounts', sa.Column('waba_verification_status', sa.String(), nullable=True))
    
    # Add opt-out fields to whatsapp_users
    op.add_column('whatsapp_users', sa.Column('opted_out', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('whatsapp_users', sa.Column('opted_out_at', sa.DateTime(), nullable=True))
    
    # Add 24-hour window tracking to whatsapp_threads
    op.add_column('whatsapp_threads', sa.Column('last_user_message_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove 24-hour window tracking from whatsapp_threads
    op.drop_column('whatsapp_threads', 'last_user_message_at')
    
    # Remove opt-out fields from whatsapp_users
    op.drop_column('whatsapp_users', 'opted_out_at')
    op.drop_column('whatsapp_users', 'opted_out')
    
    # Remove waba_verification_status from whatsapp_accounts
    op.drop_column('whatsapp_accounts', 'waba_verification_status')
    
    # Remove messaging_service_sid from whatsapp_accounts
    op.drop_index(op.f('ix_whatsapp_accounts_messaging_service_sid'), table_name='whatsapp_accounts')
    op.drop_column('whatsapp_accounts', 'messaging_service_sid')
