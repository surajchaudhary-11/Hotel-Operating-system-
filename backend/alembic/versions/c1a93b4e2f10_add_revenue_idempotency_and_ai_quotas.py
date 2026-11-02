"""add revenue idempotency and ai quotas

Revision ID: c1a93b4e2f10
Revises: 8b509fc2873d
Create Date: 2026-11-02 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a93b4e2f10'
down_revision: Union[str, None] = '8b509fc2873d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Financial integrity check: detect conflicting duplicate revenue records before modifying schema
    res = bind.execute(sa.text("""
        SELECT hotel_id, stay_id, posting_date, revenue_type, COUNT(id) as count
        FROM revenues
        WHERE stay_id IS NOT NULL
        GROUP BY hotel_id, stay_id, posting_date, revenue_type
        HAVING COUNT(id) > 1
    """))
    conflicts = res.fetchall()
    if conflicts:
        details = [f"Stay {c[1]} on {c[2]} ({c[3]}): {c[4]} records" for c in conflicts]
        raise RuntimeError(
            f"MIGRATION ABORTED: Found {len(conflicts)} conflicting duplicate revenue records. "
            f"Financial integrity rule prohibits automated deletion. Manual ledger reconciliation is required. "
            f"Details: {details}"
        )

    # 2. Add idempotency_key column to revenues
    op.add_column('revenues', sa.Column('idempotency_key', sa.String(length=100), nullable=True))

    # 3. Backfill idempotency_key for existing audit room tariffs
    bind.execute(sa.text("""
        UPDATE revenues
        SET idempotency_key = 'audit:' || hotel_id || ':' || stay_id || ':' || posting_date || ':' || revenue_type
        WHERE revenue_type = 'ROOM_TARIFF' AND stay_id IS NOT NULL AND idempotency_key IS NULL
    """))

    # 4. Create unique index on idempotency_key
    op.create_index(op.f('ix_revenues_idempotency_key'), 'revenues', ['idempotency_key'], unique=True)

    # 5. Create tenant_ai_quotas table
    op.create_table(
        'tenant_ai_quotas',
        sa.Column('hotel_id', sa.String(length=36), nullable=False),
        sa.Column('daily_request_limit', sa.Integer(), nullable=False, server_default='500'),
        sa.Column('monthly_request_limit', sa.Integer(), nullable=False, server_default='5000'),
        sa.Column('monthly_budget_usd', sa.Numeric(precision=10, scale=2), nullable=False, server_default='20.00'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['hotel_id'], ['hotels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('hotel_id')
    )

    # 6. Create tenant_ai_usage table
    op.create_table(
        'tenant_ai_usage',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('hotel_id', sa.String(length=36), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_cost', sa.Numeric(precision=10, scale=6), nullable=False, server_default='0.000000'),
        sa.Column('request_status', sa.String(length=20), nullable=False, server_default='SUCCESS'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_date', sa.Date(), nullable=False),
        sa.Column('period_month', sa.String(length=7), nullable=False),
        sa.ForeignKeyConstraint(['hotel_id'], ['hotels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenant_ai_usage_hotel_id'), 'tenant_ai_usage', ['hotel_id'], unique=False)
    op.create_index(op.f('ix_tenant_ai_usage_period_date'), 'tenant_ai_usage', ['period_date'], unique=False)
    op.create_index(op.f('ix_tenant_ai_usage_period_month'), 'tenant_ai_usage', ['period_month'], unique=False)
    op.create_index('ix_tenant_ai_usage_hotel_period', 'tenant_ai_usage', ['hotel_id', 'period_month'], unique=False)
    op.create_index('ix_tenant_ai_usage_hotel_date', 'tenant_ai_usage', ['hotel_id', 'period_date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_tenant_ai_usage_hotel_date', table_name='tenant_ai_usage')
    op.drop_index('ix_tenant_ai_usage_hotel_period', table_name='tenant_ai_usage')
    op.drop_index(op.f('ix_tenant_ai_usage_period_month'), table_name='tenant_ai_usage')
    op.drop_index(op.f('ix_tenant_ai_usage_period_date'), table_name='tenant_ai_usage')
    op.drop_index(op.f('ix_tenant_ai_usage_hotel_id'), table_name='tenant_ai_usage')
    op.drop_table('tenant_ai_usage')
    op.drop_table('tenant_ai_quotas')
    op.drop_index(op.f('ix_revenues_idempotency_key'), table_name='revenues')
    op.drop_column('revenues', 'idempotency_key')
