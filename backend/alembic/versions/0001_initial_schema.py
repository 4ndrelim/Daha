"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-11-17 01:45:10.975490

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table('ai_cache',
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('conversations',
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('transaction_id', sa.Integer(), nullable=True),
    sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('transaction_id')
    )
    op.create_table('places',
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('lat', sa.Float(), nullable=False),
    sa.Column('lng', sa.Float(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('email', sa.Text(), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('avatar_url', sa.Text(), nullable=True),
    sa.Column('bio', sa.Text(), nullable=True),
    sa.Column('walking_radius_min', sa.Integer(), server_default='10', nullable=False),
    sa.Column('onboarded', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('is_demo', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('referred_by', sa.Integer(), nullable=True),
    sa.Column('seed_key', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['referred_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('seed_key')
    )
    op.create_table('communities',
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('slug', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('emoji', sa.Text(), nullable=True),
    sa.Column('group_type', sa.String(length=20), nullable=True),
    sa.Column('is_private', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('join_code', sa.Text(), nullable=True),
    sa.Column('lat', sa.Float(), nullable=True),
    sa.Column('lng', sa.Float(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('seed_key', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('seed_key'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('conversation_participants',
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('last_read_message_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('conversation_id', 'user_id')
    )
    op.create_index('ix_conversation_participants_user_id', 'conversation_participants', ['user_id'], unique=False)
    op.create_table('events',
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('messages',
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=True),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_conversation_id_id', 'messages', ['conversation_id', 'id'], unique=False)
    op.create_table('notifications',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('link', sa.Text(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notifications_user_id_read_at', 'notifications', ['user_id', 'read_at'], unique=False)
    op.create_table('points_ledger',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('delta', sa.Integer(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('ref_type', sa.Text(), nullable=True),
    sa.Column('ref_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_points_ledger_user_id'), 'points_ledger', ['user_id'], unique=False)
    op.create_table('requests',
    sa.Column('requester_id', sa.Integer(), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('item_name', sa.Text(), nullable=True),
    sa.Column('category', sa.String(length=20), nullable=True),
    sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
    sa.Column('needed_from', sa.Date(), nullable=True),
    sa.Column('needed_until', sa.Date(), nullable=True),
    sa.Column('duration_days', sa.Integer(), nullable=True),
    sa.Column('transaction_type', sa.String(length=20), nullable=True),
    sa.Column('visibility', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='open', nullable=False),
    sa.Column('pickup_place_id', sa.Integer(), nullable=True),
    sa.Column('seed_key', sa.Text(), nullable=True),
    sa.Column('matching_status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('ai_enriched', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True),
    sa.Column('search_tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', coalesce(title, '') || ' ' || coalesce(item_name, '') || ' ' || coalesce(raw_text, ''))", persisted=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('fulfilled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['pickup_place_id'], ['places.id'], ),
    sa.ForeignKeyConstraint(['requester_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('seed_key')
    )
    op.create_index('ix_requests_embedding_hnsw', 'requests', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index(op.f('ix_requests_requester_id'), 'requests', ['requester_id'], unique=False)
    op.create_index('ix_requests_search_tsv', 'requests', ['search_tsv'], unique=False, postgresql_using='gin')
    op.create_index('ix_requests_status', 'requests', ['status'], unique=False)
    op.create_table('scans',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('provider', sa.Text(), nullable=False),
    sa.Column('model', sa.Text(), nullable=True),
    sa.Column('prompt_version', sa.Text(), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scans_user_id'), 'scans', ['user_id'], unique=False)
    op.create_table('search_logs',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('raw_query', sa.Text(), nullable=False),
    sa.Column('parsed', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('result_item_ids', postgresql.ARRAY(sa.Integer()), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('uploads',
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('path', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('width', sa.Integer(), nullable=False),
    sa.Column('height', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_uploads_owner_id'), 'uploads', ['owner_id'], unique=False)
    op.create_table('user_badges',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('earned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'code')
    )
    op.create_table('memberships',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('community_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=20), server_default='member', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'community_id')
    )
    op.create_index('ix_memberships_community_id', 'memberships', ['community_id'], unique=False)
    op.create_table('request_audiences',
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('community_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ),
    sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ),
    sa.PrimaryKeyConstraint('request_id', 'community_id')
    )
    op.create_index('ix_request_audiences_community_id', 'request_audiences', ['community_id'], unique=False)
    op.create_table('scan_images',
    sa.Column('scan_id', sa.Integer(), nullable=False),
    sa.Column('upload_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('cost_usd', sa.Float(), nullable=True),
    sa.Column('raw_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ),
    sa.ForeignKeyConstraint(['upload_id'], ['uploads.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scan_images_scan_id'), 'scan_images', ['scan_id'], unique=False)
    op.create_table('scan_detections',
    sa.Column('scan_id', sa.Integer(), nullable=False),
    sa.Column('scan_image_id', sa.Integer(), nullable=False),
    sa.Column('image_index', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('condition_guess', sa.String(length=20), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('bbox', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('suggested_share', sa.Boolean(), nullable=False),
    sa.Column('sensitive_reason', sa.Text(), nullable=True),
    sa.Column('suggested_transaction_type', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('published_item_id', sa.Integer(), nullable=True),
    sa.Column('edits', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ),
    sa.ForeignKeyConstraint(['scan_image_id'], ['scan_images.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scan_detections_scan_id'), 'scan_detections', ['scan_id'], unique=False)
    op.create_table('items',
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
    sa.Column('condition', sa.String(length=20), nullable=True),
    sa.Column('transaction_type', sa.String(length=20), nullable=False),
    sa.Column('max_lend_days', sa.Integer(), nullable=True),
    sa.Column('available_from', sa.Date(), nullable=True),
    sa.Column('available_until', sa.Date(), nullable=True),
    sa.Column('visibility', sa.String(length=20), nullable=False),
    sa.Column('pings_enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('status', sa.String(length=20), server_default='available', nullable=False),
    sa.Column('archived', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('pickup_place_id', sa.Integer(), nullable=True),
    sa.Column('pickup_note', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), server_default='manual', nullable=False),
    sa.Column('scan_detection_id', sa.Integer(), nullable=True),
    sa.Column('seed_key', sa.Text(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True),
    sa.Column('search_tsv', postgresql.TSVECTOR(), sa.Computed("setweight(to_tsvector('english', coalesce(name, '')), 'A') || setweight(to_tsvector('english', coalesce(description, '')), 'B')", persisted=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['pickup_place_id'], ['places.id'], ),
    sa.ForeignKeyConstraint(['scan_detection_id'], ['scan_detections.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('seed_key')
    )
    op.create_index('ix_items_embedding_hnsw', 'items', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_items_name_trgm', 'items', ['name'], unique=False, postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_index('ix_items_owner_id', 'items', ['owner_id'], unique=False)
    op.create_index('ix_items_search_tsv', 'items', ['search_tsv'], unique=False, postgresql_using='gin')
    op.create_index('ix_items_status_active', 'items', ['status'], unique=False, postgresql_where=sa.text('NOT archived'))
    op.create_table('item_audiences',
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('community_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
    sa.PrimaryKeyConstraint('item_id', 'community_id')
    )
    op.create_index('ix_item_audiences_community_id', 'item_audiences', ['community_id'], unique=False)
    op.create_table('item_images',
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('upload_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
    sa.ForeignKeyConstraint(['upload_id'], ['uploads.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_item_images_item_id'), 'item_images', ['item_id'], unique=False)
    op.create_table('request_matches',
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('notified', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('anonymous', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
    sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ),
    sa.PrimaryKeyConstraint('request_id', 'item_id')
    )
    op.create_index('ix_request_matches_item_id', 'request_matches', ['item_id'], unique=False)
    op.create_table('transactions',
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('request_id', sa.Integer(), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=False),
    sa.Column('initiated_by', sa.String(length=20), nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('pickup_place_id', sa.Integer(), nullable=True),
    sa.Column('pickup_note', sa.Text(), nullable=True),
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('handed_off_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('declined_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['borrower_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['pickup_place_id'], ['places.id'], ),
    sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_transactions_borrower_id', 'transactions', ['borrower_id'], unique=False)
    op.create_index('ix_transactions_item_id', 'transactions', ['item_id'], unique=False)
    op.create_index('ix_transactions_owner_id', 'transactions', ['owner_id'], unique=False)
    op.create_index('ix_transactions_request_id', 'transactions', ['request_id'], unique=False)
    op.create_foreign_key('fk_conversations_transaction_id', 'conversations', 'transactions', ['transaction_id'], ['id'])
    op.create_table('reviews',
    sa.Column('transaction_id', sa.Integer(), nullable=False),
    sa.Column('reviewer_id', sa.Integer(), nullable=False),
    sa.Column('reviewee_id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.SmallInteger(), nullable=False),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['reviewee_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('transaction_id', 'reviewer_id', name='uq_reviews_tx_reviewer')
    )
    op.create_index(op.f('ix_reviews_reviewee_id'), 'reviews', ['reviewee_id'], unique=False)
    op.create_table('transaction_events',
    sa.Column('transaction_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transaction_events_transaction_id'), 'transaction_events', ['transaction_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_conversations_transaction_id', 'conversations', type_='foreignkey')
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_transaction_events_transaction_id'), table_name='transaction_events')
    op.drop_table('transaction_events')
    op.drop_index(op.f('ix_reviews_reviewee_id'), table_name='reviews')
    op.drop_table('reviews')
    op.drop_index('ix_transactions_request_id', table_name='transactions')
    op.drop_index('ix_transactions_owner_id', table_name='transactions')
    op.drop_index('ix_transactions_item_id', table_name='transactions')
    op.drop_index('ix_transactions_borrower_id', table_name='transactions')
    op.drop_table('transactions')
    op.drop_index('ix_request_matches_item_id', table_name='request_matches')
    op.drop_table('request_matches')
    op.drop_index(op.f('ix_item_images_item_id'), table_name='item_images')
    op.drop_table('item_images')
    op.drop_index('ix_item_audiences_community_id', table_name='item_audiences')
    op.drop_table('item_audiences')
    op.drop_index('ix_items_status_active', table_name='items', postgresql_where=sa.text('NOT archived'))
    op.drop_index('ix_items_search_tsv', table_name='items', postgresql_using='gin')
    op.drop_index('ix_items_owner_id', table_name='items')
    op.drop_index('ix_items_name_trgm', table_name='items', postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.drop_index('ix_items_embedding_hnsw', table_name='items', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('items')
    op.drop_index(op.f('ix_scan_detections_scan_id'), table_name='scan_detections')
    op.drop_table('scan_detections')
    op.drop_index(op.f('ix_scan_images_scan_id'), table_name='scan_images')
    op.drop_table('scan_images')
    op.drop_index('ix_request_audiences_community_id', table_name='request_audiences')
    op.drop_table('request_audiences')
    op.drop_index('ix_memberships_community_id', table_name='memberships')
    op.drop_table('memberships')
    op.drop_table('user_badges')
    op.drop_index(op.f('ix_uploads_owner_id'), table_name='uploads')
    op.drop_table('uploads')
    op.drop_table('search_logs')
    op.drop_index(op.f('ix_scans_user_id'), table_name='scans')
    op.drop_table('scans')
    op.drop_index('ix_requests_status', table_name='requests')
    op.drop_index('ix_requests_search_tsv', table_name='requests', postgresql_using='gin')
    op.drop_index(op.f('ix_requests_requester_id'), table_name='requests')
    op.drop_index('ix_requests_embedding_hnsw', table_name='requests', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('requests')
    op.drop_index(op.f('ix_points_ledger_user_id'), table_name='points_ledger')
    op.drop_table('points_ledger')
    op.drop_index('ix_notifications_user_id_read_at', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index('ix_messages_conversation_id_id', table_name='messages')
    op.drop_table('messages')
    op.drop_table('events')
    op.drop_index('ix_conversation_participants_user_id', table_name='conversation_participants')
    op.drop_table('conversation_participants')
    op.drop_table('communities')
    op.drop_table('users')
    op.drop_table('places')
    op.drop_table('conversations')
    op.drop_table('ai_cache')
    # ### end Alembic commands ###
