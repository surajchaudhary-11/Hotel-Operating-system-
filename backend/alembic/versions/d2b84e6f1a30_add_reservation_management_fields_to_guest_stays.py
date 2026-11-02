"""add reservation management fields to guest stays

Revision ID: d2b84e6f1a30
Revises: c1a93b4e2f10
Create Date: 2026-11-02 10:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2b84e6f1a30'
down_revision: Union[str, None] = 'c1a93b4e2f10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('guest_stays', schema=None) as batch_op:
        batch_op.add_column(sa.Column('booking_reference', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('booking_source', sa.String(length=30), server_default='DIRECT', nullable=False))
        batch_op.add_column(sa.Column('external_reference_id', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('group_booking_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('special_requests', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('estimated_arrival_time', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('payment_status', sa.String(length=20), server_default='UNPAID', nullable=False))
        batch_op.add_column(sa.Column('cancellation_reason', sa.Text(), nullable=True))
        batch_op.create_index('ix_guest_stays_booking_reference', ['booking_reference'], unique=True)
        batch_op.create_index('ix_guest_stays_group_booking_id', ['group_booking_id'], unique=False)

    # Backfill existing guest_stays with generated booking references if null
    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE guest_stays 
        SET booking_reference = 'BK-LEGACY-' || substr(id, 1, 8) 
        WHERE booking_reference IS NULL
    """))


def downgrade() -> None:
    with op.batch_alter_table('guest_stays', schema=None) as batch_op:
        batch_op.drop_index('ix_guest_stays_group_booking_id')
        batch_op.drop_index('ix_guest_stays_booking_reference')
        batch_op.drop_column('cancellation_reason')
        batch_op.drop_column('payment_status')
        batch_op.drop_column('estimated_arrival_time')
        batch_op.drop_column('special_requests')
        batch_op.drop_column('group_booking_id')
        batch_op.drop_column('external_reference_id')
        batch_op.drop_column('booking_source')
        batch_op.drop_column('booking_reference')
