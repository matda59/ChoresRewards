"""Add vehicle_service table

Revision ID: 001_add_vehicle_service
Revises: 
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = '001_add_vehicle_service'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'vehicle_service',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organise_item_id', sa.Integer(),
                  sa.ForeignKey('organise_item.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_type', sa.String(200), nullable=False),
        sa.Column('service_date', sa.Date(), nullable=True),
        sa.Column('mileage', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('provider', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_vehicle_service_organise_item_id', 'vehicle_service', ['organise_item_id'])


def downgrade():
    op.drop_index('ix_vehicle_service_organise_item_id', table_name='vehicle_service')
    op.drop_table('vehicle_service')
