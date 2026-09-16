"""Initial schema — the six tables the portal already had.

This is the starting line, not a change. It recreates exactly what
``seed.py`` used to build directly: customers, users, orders, shipments,
documents and notifications. A brand-new database gets all of it by running
this migration; the existing development database is simply marked as
already being at this point (see ``migrate.py``).

Revision: 0001
Previous: none — this is the first
Created:  2026-09-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this change."""
    op.create_table('customers',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('country', sa.String(length=100), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_code'), 'customers', ['code'], unique=True)
    op.create_table('orders',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('sales_order_no', sa.String(length=140), nullable=False),
    sa.Column('customer_po', sa.String(length=140), nullable=True),
    sa.Column('grade', sa.String(length=140), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('ordered_qty', sa.Numeric(precision=14, scale=3), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_customer_id'), 'orders', ['customer_id'], unique=False)
    op.create_index(op.f('ix_orders_sales_order_no'), 'orders', ['sales_order_no'], unique=True)
    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_customer_id'), 'users', ['customer_id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('shipments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('shipment_no', sa.String(length=140), nullable=False),
    sa.Column('dispatched_qty', sa.Numeric(precision=14, scale=3), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('vessel_name', sa.String(length=140), nullable=True),
    sa.Column('imo_number', sa.String(length=20), nullable=True),
    sa.Column('etd', sa.Date(), nullable=True),
    sa.Column('eta', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_shipments_order_id'), 'shipments', ['order_id'], unique=False)
    op.create_index(op.f('ix_shipments_shipment_no'), 'shipments', ['shipment_no'], unique=False)
    op.create_table('documents',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('shipment_id', sa.Integer(), nullable=False),
    sa.Column('doc_type', sa.String(length=60), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('stored_path', sa.String(length=500), nullable=True),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_shipment_id'), 'documents', ['shipment_id'], unique=False)
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('shipment_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('event', sa.String(length=50), nullable=False),
    sa.Column('channel', sa.String(length=20), nullable=False),
    sa.Column('outcome', sa.String(length=20), nullable=False),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('shipment_id', 'event', 'user_id', name='uq_notification_once')
    )
    op.create_index(op.f('ix_notifications_shipment_id'), 'notifications', ['shipment_id'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)


def downgrade() -> None:
    """Undo this change."""
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_shipment_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_documents_shipment_id'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_shipments_shipment_no'), table_name='shipments')
    op.drop_index(op.f('ix_shipments_order_id'), table_name='shipments')
    op.drop_table('shipments')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_customer_id'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_orders_sales_order_no'), table_name='orders')
    op.drop_index(op.f('ix_orders_customer_id'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_customers_code'), table_name='customers')
    op.drop_table('customers')
