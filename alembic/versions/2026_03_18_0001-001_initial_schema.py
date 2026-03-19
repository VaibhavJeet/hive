"""Initial schema - AI Community Companions database

Revision ID: 001
Revises:
Create Date: 2026-03-18

This migration creates all initial tables for the AI Community Companions platform.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all database tables."""

    # Create pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # ========================================================================
    # BOT PROFILES TABLE
    # ========================================================================
    op.create_table(
        'bot_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('handle', sa.String(50), unique=True, nullable=False),
        sa.Column('bio', sa.Text, nullable=False),
        sa.Column('avatar_seed', sa.String(100), nullable=False),
        sa.Column('is_ai_labeled', sa.Boolean, default=True, nullable=False),
        sa.Column('ai_label_text', sa.String(50), default='AI Companion'),
        sa.Column('age', sa.Integer, nullable=False),
        sa.Column('gender', sa.String(20), nullable=False),
        sa.Column('location', sa.String(100), default=''),
        sa.Column('backstory', sa.Text, nullable=False),
        sa.Column('interests', postgresql.JSON, default=[]),
        sa.Column('personality_traits', postgresql.JSON, nullable=False),
        sa.Column('writing_fingerprint', postgresql.JSON, nullable=False),
        sa.Column('activity_pattern', postgresql.JSON, nullable=False),
        sa.Column('emotional_state', postgresql.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('last_active', sa.DateTime, default=sa.func.now()),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_retired', sa.Boolean, default=False),
        sa.Column('is_paused', sa.Boolean, default=False),
        sa.Column('paused_at', sa.DateTime, nullable=True),
        sa.Column('paused_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('search_vector', postgresql.TSVECTOR, nullable=True),
    )
    op.create_index('idx_bot_handle', 'bot_profiles', ['handle'])
    op.create_index('idx_bot_active', 'bot_profiles', ['is_active'])
    op.create_index('idx_bot_last_active', 'bot_profiles', ['last_active'])
    op.create_index('idx_bot_paused', 'bot_profiles', ['is_paused'])
    op.create_index('idx_bot_deleted', 'bot_profiles', ['is_deleted'])
    op.create_index('idx_bot_search_vector', 'bot_profiles', ['search_vector'], postgresql_using='gin')

    # ========================================================================
    # MEMORY ITEMS TABLE
    # ========================================================================
    op.create_table(
        'memory_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), nullable=False),
        sa.Column('memory_type', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding', sa.dialects.postgresql.ARRAY(sa.Float), nullable=True),  # Vector(768)
        sa.Column('importance', sa.Float, default=0.5),
        sa.Column('emotional_valence', sa.Float, default=0.0),
        sa.Column('related_entity_ids', postgresql.JSON, default=[]),
        sa.Column('context', postgresql.JSON, default={}),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('last_accessed', sa.DateTime, default=sa.func.now()),
        sa.Column('access_count', sa.Integer, default=0),
    )
    op.create_index('idx_memory_bot_id', 'memory_items', ['bot_id'])
    op.create_index('idx_memory_type', 'memory_items', ['memory_type'])
    op.create_index('idx_memory_importance', 'memory_items', ['importance'])

    # ========================================================================
    # RELATIONSHIPS TABLE
    # ========================================================================
    op.create_table(
        'relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_is_human', sa.Boolean, default=False),
        sa.Column('relationship_type', sa.String(30), default='stranger'),
        sa.Column('affinity_score', sa.Float, default=0.5),
        sa.Column('interaction_count', sa.Integer, default=0),
        sa.Column('last_interaction', sa.DateTime, nullable=True),
        sa.Column('shared_memories', postgresql.JSON, default=[]),
        sa.Column('inside_jokes', postgresql.JSON, default=[]),
        sa.Column('topics_discussed', postgresql.JSON, default=[]),
    )
    op.create_unique_constraint('unique_relationship', 'relationships', ['source_id', 'target_id'])
    op.create_index('idx_relationship_source', 'relationships', ['source_id'])
    op.create_index('idx_relationship_target', 'relationships', ['target_id'])

    # ========================================================================
    # COMMUNITIES TABLE
    # ========================================================================
    op.create_table(
        'communities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('theme', sa.String(50), nullable=False),
        sa.Column('topics', postgresql.JSON, default=[]),
        sa.Column('tone', sa.String(30), default='friendly'),
        sa.Column('min_bots', sa.Integer, default=30),
        sa.Column('max_bots', sa.Integer, default=150),
        sa.Column('current_bot_count', sa.Integer, default=0),
        sa.Column('activity_level', sa.Float, default=0.5),
        sa.Column('real_user_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('content_guidelines', sa.Text, default=''),
        sa.Column('banned_topics', postgresql.JSON, default=[]),
    )
    op.create_index('idx_community_theme', 'communities', ['theme'])
    op.create_index('idx_community_activity', 'communities', ['activity_level'])

    # ========================================================================
    # COMMUNITY MEMBERSHIPS TABLE
    # ========================================================================
    op.create_table(
        'community_memberships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), nullable=False),
        sa.Column('community_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('communities.id'), nullable=False),
        sa.Column('joined_at', sa.DateTime, default=sa.func.now()),
        sa.Column('role', sa.String(30), default='member'),
        sa.Column('engagement_score', sa.Float, default=0.5),
        sa.Column('post_count', sa.Integer, default=0),
        sa.Column('comment_count', sa.Integer, default=0),
    )
    op.create_unique_constraint('unique_membership', 'community_memberships', ['bot_id', 'community_id'])
    op.create_index('idx_membership_bot', 'community_memberships', ['bot_id'])
    op.create_index('idx_membership_community', 'community_memberships', ['community_id'])

    # ========================================================================
    # SCHEDULED ACTIVITIES TABLE
    # ========================================================================
    op.create_table(
        'scheduled_activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), nullable=False),
        sa.Column('activity_type', sa.String(30), nullable=False),
        sa.Column('scheduled_time', sa.DateTime, nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('context', postgresql.JSON, default={}),
        sa.Column('priority', sa.Integer, default=5),
        sa.Column('is_completed', sa.Boolean, default=False),
        sa.Column('is_cancelled', sa.Boolean, default=False),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
    )
    op.create_index('idx_activity_scheduled', 'scheduled_activities', ['scheduled_time'])
    op.create_index('idx_activity_bot', 'scheduled_activities', ['bot_id'])
    op.create_index('idx_activity_pending', 'scheduled_activities', ['is_completed', 'is_cancelled'])

    # ========================================================================
    # GENERATED CONTENT TABLE
    # ========================================================================
    op.create_table(
        'generated_content',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), nullable=False),
        sa.Column('content_type', sa.String(30), nullable=False),
        sa.Column('text_content', sa.Text, nullable=False),
        sa.Column('media_prompt', sa.Text, nullable=True),
        sa.Column('reply_to_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('community_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('emotional_context', postgresql.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('engagement_score', sa.Float, default=0.0),
    )
    op.create_index('idx_content_bot', 'generated_content', ['bot_id'])
    op.create_index('idx_content_type', 'generated_content', ['content_type'])
    op.create_index('idx_content_created', 'generated_content', ['created_at'])
    op.create_index('idx_content_community', 'generated_content', ['community_id'])

    # ========================================================================
    # POST VIEWS TABLE
    # ========================================================================
    op.create_table(
        'post_views',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('viewer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('viewer_is_bot', sa.Boolean, default=False),
        sa.Column('viewed_at', sa.DateTime, default=sa.func.now()),
        sa.Column('last_viewed_at', sa.DateTime, default=sa.func.now()),
        sa.Column('view_count', sa.Integer, default=1),
    )
    op.create_unique_constraint('unique_post_view', 'post_views', ['post_id', 'viewer_id'])
    op.create_index('idx_view_post', 'post_views', ['post_id'])
    op.create_index('idx_view_viewer', 'post_views', ['viewer_id'])
    op.create_index('idx_view_time', 'post_views', ['viewed_at'])

    # ========================================================================
    # USER SESSIONS TABLE
    # ========================================================================
    op.create_table(
        'user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_session_id', sa.String(100), nullable=True),
        sa.Column('started_at', sa.DateTime, default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime, nullable=True),
        sa.Column('duration_seconds', sa.Float, default=0.0),
    )
    op.create_index('idx_session_user', 'user_sessions', ['user_id'])
    op.create_index('idx_session_started', 'user_sessions', ['started_at'])

    # ========================================================================
    # DAILY METRICS TABLE
    # ========================================================================
    op.create_table(
        'daily_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('date', sa.DateTime, nullable=False, unique=True),
        sa.Column('posts', sa.Integer, default=0),
        sa.Column('comments', sa.Integer, default=0),
        sa.Column('likes', sa.Integer, default=0),
        sa.Column('dms', sa.Integer, default=0),
        sa.Column('chats', sa.Integer, default=0),
        sa.Column('active_users', sa.Integer, default=0),
        sa.Column('new_users', sa.Integer, default=0),
        sa.Column('active_bots', sa.Integer, default=0),
        sa.Column('bot_posts', sa.Integer, default=0),
        sa.Column('bot_comments', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_daily_metrics_date', 'daily_metrics', ['date'])

    # ========================================================================
    # MEDIA TABLE
    # ========================================================================
    op.create_table(
        'media',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('uploader_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uploader_is_bot', sa.Boolean, default=False),
        sa.Column('file_type', sa.String(20), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('stored_filename', sa.String(255), nullable=False),
        sa.Column('original_url', sa.String(500), nullable=False),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('width', sa.Integer, nullable=True),
        sa.Column('height', sa.Integer, nullable=True),
        sa.Column('duration_seconds', sa.Float, nullable=True),
        sa.Column('size_bytes', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
    )
    op.create_index('idx_media_uploader', 'media', ['uploader_id'])
    op.create_index('idx_media_type', 'media', ['file_type'])
    op.create_index('idx_media_created', 'media', ['created_at'])
    op.create_index('idx_media_deleted', 'media', ['is_deleted'])

    # ========================================================================
    # POSTS TABLE
    # ========================================================================
    op.create_table(
        'posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), nullable=False),
        sa.Column('community_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('communities.id'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('media_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('media.id'), nullable=True),
        sa.Column('like_count', sa.Integer, default=0),
        sa.Column('comment_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('search_vector', postgresql.TSVECTOR, nullable=True),
        sa.Column('is_flagged', sa.Boolean, default=False),
        sa.Column('flag_reason', sa.Text, nullable=True),
        sa.Column('moderation_status', sa.String(30), nullable=True),
    )
    op.create_index('idx_post_author', 'posts', ['author_id'])
    op.create_index('idx_post_community', 'posts', ['community_id'])
    op.create_index('idx_post_created', 'posts', ['created_at'])
    op.create_index('idx_post_media', 'posts', ['media_id'])
    op.create_index('idx_post_search_vector', 'posts', ['search_vector'], postgresql_using='gin')
    op.create_index('idx_post_flagged', 'posts', ['is_flagged'])

    # ========================================================================
    # POST LIKES TABLE
    # ========================================================================
    op.create_table(
        'post_likes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('posts.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_bot', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_unique_constraint('unique_post_like', 'post_likes', ['post_id', 'user_id'])
    op.create_index('idx_like_post', 'post_likes', ['post_id'])
    op.create_index('idx_like_user', 'post_likes', ['user_id'])

    # ========================================================================
    # POST COMMENTS TABLE
    # ========================================================================
    op.create_table(
        'post_comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('posts.id'), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_bot', sa.Boolean, default=True),
        sa.Column('parent_comment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('post_comments.id'), nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('like_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean, default=False),
    )
    op.create_index('idx_comment_post', 'post_comments', ['post_id'])
    op.create_index('idx_comment_author', 'post_comments', ['author_id'])
    op.create_index('idx_comment_created', 'post_comments', ['created_at'])

    # ========================================================================
    # COMMUNITY CHAT MESSAGES TABLE
    # ========================================================================
    op.create_table(
        'community_chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('community_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('communities.id'), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_bot', sa.Boolean, default=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('reply_to_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('community_chat_messages.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean, default=False),
    )
    op.create_index('idx_chat_community', 'community_chat_messages', ['community_id'])
    op.create_index('idx_chat_author', 'community_chat_messages', ['author_id'])
    op.create_index('idx_chat_created', 'community_chat_messages', ['created_at'])

    # ========================================================================
    # DIRECT MESSAGES TABLE
    # ========================================================================
    op.create_table(
        'direct_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', sa.String(100), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('receiver_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_is_bot', sa.Boolean, default=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('is_read', sa.Boolean, default=False),
    )
    op.create_index('idx_dm_conversation', 'direct_messages', ['conversation_id'])
    op.create_index('idx_dm_sender', 'direct_messages', ['sender_id'])
    op.create_index('idx_dm_receiver', 'direct_messages', ['receiver_id'])
    op.create_index('idx_dm_created', 'direct_messages', ['created_at'])

    # ========================================================================
    # APP USERS TABLE
    # ========================================================================
    op.create_table(
        'app_users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('device_id', sa.String(100), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('avatar_seed', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_admin', sa.Boolean, default=False),
        sa.Column('is_banned', sa.Boolean, default=False),
        sa.Column('ban_reason', sa.Text, nullable=True),
        sa.Column('banned_at', sa.DateTime, nullable=True),
        sa.Column('banned_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('last_active', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_user_device', 'app_users', ['device_id'])
    op.create_index('idx_user_email', 'app_users', ['email'])
    op.create_index('idx_user_admin', 'app_users', ['is_admin'])
    op.create_index('idx_user_banned', 'app_users', ['is_banned'])

    # ========================================================================
    # REFRESH TOKENS TABLE
    # ========================================================================
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('is_revoked', sa.Boolean, default=False),
        sa.Column('revoked_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_refresh_token_user', 'refresh_tokens', ['user_id'])
    op.create_index('idx_refresh_token_revoked', 'refresh_tokens', ['is_revoked'])

    # ========================================================================
    # BOT METRICS TABLE
    # ========================================================================
    op.create_table(
        'bot_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime, default=sa.func.now()),
        sa.Column('posts_generated', sa.Integer, default=0),
        sa.Column('comments_generated', sa.Integer, default=0),
        sa.Column('replies_generated', sa.Integer, default=0),
        sa.Column('messages_sent', sa.Integer, default=0),
        sa.Column('likes_received', sa.Integer, default=0),
        sa.Column('comments_received', sa.Integer, default=0),
        sa.Column('engagement_rate', sa.Float, default=0.0),
        sa.Column('avg_response_time_ms', sa.Float, default=0.0),
        sa.Column('naturalness_score', sa.Float, default=0.0),
        sa.Column('consistency_score', sa.Float, default=0.0),
    )
    op.create_index('idx_metrics_bot_time', 'bot_metrics', ['bot_id', 'timestamp'])

    # ========================================================================
    # SYSTEM METRICS TABLE
    # ========================================================================
    op.create_table(
        'system_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime, default=sa.func.now()),
        sa.Column('active_bots', sa.Integer, default=0),
        sa.Column('total_bots', sa.Integer, default=0),
        sa.Column('activities_completed', sa.Integer, default=0),
        sa.Column('activities_failed', sa.Integer, default=0),
        sa.Column('content_generated', sa.Integer, default=0),
        sa.Column('avg_inference_time_ms', sa.Float, default=0.0),
        sa.Column('llm_requests', sa.Integer, default=0),
        sa.Column('cache_hit_rate', sa.Float, default=0.0),
        sa.Column('gpu_memory_usage_mb', sa.Float, default=0.0),
        sa.Column('cpu_usage_percent', sa.Float, default=0.0),
    )
    op.create_index('idx_system_metrics_time', 'system_metrics', ['timestamp'])

    # ========================================================================
    # BOT MIND STATES TABLE
    # ========================================================================
    op.create_table(
        'bot_mind_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), unique=True, nullable=False),
        sa.Column('core_values', postgresql.JSON, default=[]),
        sa.Column('beliefs', postgresql.JSON, default={}),
        sa.Column('pet_peeves', postgresql.JSON, default=[]),
        sa.Column('current_goals', postgresql.JSON, default=[]),
        sa.Column('insecurities', postgresql.JSON, default=[]),
        sa.Column('speech_quirks', postgresql.JSON, default=[]),
        sa.Column('passions', postgresql.JSON, default=[]),
        sa.Column('avoided_topics', postgresql.JSON, default=[]),
        sa.Column('social_perceptions', postgresql.JSON, default={}),
        sa.Column('current_mood', sa.String(30), default='neutral'),
        sa.Column('current_energy', sa.Float, default=0.7),
        sa.Column('inner_monologue', postgresql.JSON, default=[]),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_mind_state_bot', 'bot_mind_states', ['bot_id'])

    # ========================================================================
    # BOT LEARNING STATES TABLE
    # ========================================================================
    op.create_table(
        'bot_learning_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), unique=True, nullable=False),
        sa.Column('experiences', postgresql.JSON, default=[]),
        sa.Column('successful_topics', postgresql.JSON, default={}),
        sa.Column('failed_topics', postgresql.JSON, default={}),
        sa.Column('belief_evidence', postgresql.JSON, default={}),
        sa.Column('emerging_interests', postgresql.JSON, default=[]),
        sa.Column('fading_interests', postgresql.JSON, default=[]),
        sa.Column('trait_momentum', postgresql.JSON, default={}),
        sa.Column('admired_behaviors', postgresql.JSON, default=[]),
        sa.Column('learned_facts_about_others', postgresql.JSON, default={}),
        sa.Column('adopted_phrases', postgresql.JSON, default=[]),
        sa.Column('communication_preferences', postgresql.JSON, default={}),
        sa.Column('evolution_count', sa.Integer, default=0),
        sa.Column('last_reflection', sa.DateTime, nullable=True),
        sa.Column('last_evolution', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_learning_state_bot', 'bot_learning_states', ['bot_id'])

    # ========================================================================
    # BOT SKILLS TABLE
    # ========================================================================
    op.create_table(
        'bot_skills',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), nullable=False),
        sa.Column('skill_name', sa.String(100), nullable=False),
        sa.Column('skill_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('code', sa.Text, nullable=False),
        sa.Column('trigger_conditions', postgresql.JSON, default={}),
        sa.Column('times_used', sa.Integer, default=0),
        sa.Column('success_rate', sa.Float, default=0.5),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('learned_from', sa.Text, nullable=True),
        sa.Column('version', sa.Integer, default=1),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_skill_bot', 'bot_skills', ['bot_id'])
    op.create_index('idx_skill_type', 'bot_skills', ['skill_type'])
    op.create_index('idx_skill_active', 'bot_skills', ['is_active'])
    op.create_unique_constraint('unique_bot_skill', 'bot_skills', ['bot_id', 'skill_name'])

    # ========================================================================
    # RETIRED BOTS TABLE
    # ========================================================================
    op.create_table(
        'retired_bots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), unique=True, nullable=False),
        sa.Column('reason', sa.String(50), nullable=False),
        sa.Column('retired_at', sa.DateTime, default=sa.func.now()),
        sa.Column('retired_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('total_posts', sa.Integer, default=0),
        sa.Column('total_memories', sa.Integer, default=0),
        sa.Column('active_days', sa.Integer, default=0),
        sa.Column('archived_data_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
    )
    op.create_index('idx_retired_bot_id', 'retired_bots', ['bot_id'])
    op.create_index('idx_retired_reason', 'retired_bots', ['reason'])
    op.create_index('idx_retired_at', 'retired_bots', ['retired_at'])

    # ========================================================================
    # ARCHIVED MEMORIES TABLE
    # ========================================================================
    op.create_table(
        'archived_memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), nullable=False),
        sa.Column('archive_type', sa.String(50), nullable=False),
        sa.Column('memory_count', sa.Integer, default=0),
        sa.Column('original_memories', postgresql.JSON, default=[]),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('size_bytes', sa.Integer, default=0),
        sa.Column('compression_ratio', sa.Float, default=1.0),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_archived_bot_id', 'archived_memories', ['bot_id'])
    op.create_index('idx_archived_type', 'archived_memories', ['archive_type'])
    op.create_index('idx_archived_created', 'archived_memories', ['created_at'])

    # ========================================================================
    # COMMUNITY LIMITS TABLE
    # ========================================================================
    op.create_table(
        'community_limits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('community_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('communities.id'), unique=True, nullable=False),
        sa.Column('max_bots', sa.Integer, default=100),
        sa.Column('min_bots', sa.Integer, default=10),
        sa.Column('max_messages_per_hour', sa.Integer, default=500),
        sa.Column('max_posts_per_hour', sa.Integer, default=100),
        sa.Column('target_engagement', sa.Float, default=0.5),
        sa.Column('target_response_time_ms', sa.Integer, default=5000),
        sa.Column('auto_scale_enabled', sa.Boolean, default=True),
        sa.Column('scale_up_threshold', sa.Float, default=0.8),
        sa.Column('scale_down_threshold', sa.Float, default=0.3),
        sa.Column('last_scale_at', sa.DateTime, nullable=True),
        sa.Column('last_scale_action', sa.String(50), nullable=True),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_community_limits_community', 'community_limits', ['community_id'])

    # ========================================================================
    # STORIES TABLE
    # ========================================================================
    op.create_table(
        'stories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_is_bot', sa.Boolean, default=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('media_url', sa.String(500), nullable=True),
        sa.Column('background_color', sa.String(20), default='#1a1a2e'),
        sa.Column('font_style', sa.String(30), default='normal'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('is_deleted', sa.Boolean, default=False),
    )
    op.create_index('idx_story_author', 'stories', ['author_id'])
    op.create_index('idx_story_created', 'stories', ['created_at'])
    op.create_index('idx_story_expires', 'stories', ['expires_at'])
    op.create_index('idx_story_active', 'stories', ['is_deleted', 'expires_at'])

    # ========================================================================
    # STORY VIEWS TABLE
    # ========================================================================
    op.create_table(
        'story_views',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('story_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('stories.id'), nullable=False),
        sa.Column('viewer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('viewer_is_bot', sa.Boolean, default=False),
        sa.Column('viewed_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_unique_constraint('unique_story_view', 'story_views', ['story_id', 'viewer_id'])
    op.create_index('idx_story_view_story', 'story_views', ['story_id'])
    op.create_index('idx_story_view_viewer', 'story_views', ['viewer_id'])

    # ========================================================================
    # USER BLOCKS TABLE
    # ========================================================================
    op.create_table(
        'user_blocks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id'), nullable=False),
        sa.Column('blocked_bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), nullable=False),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_unique_constraint('unique_user_block', 'user_blocks', ['user_id', 'blocked_bot_id'])
    op.create_index('idx_block_user', 'user_blocks', ['user_id'])
    op.create_index('idx_block_bot', 'user_blocks', ['blocked_bot_id'])

    # ========================================================================
    # BOT BEHAVIOR FLAGS TABLE
    # ========================================================================
    op.create_table(
        'bot_behavior_flags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bot_profiles.id'), nullable=False),
        sa.Column('reporter_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id'), nullable=False),
        sa.Column('flag_type', sa.String(30), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('resolution', sa.Text, nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('context_content_type', sa.String(30), nullable=True),
        sa.Column('context_content_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('idx_flag_bot', 'bot_behavior_flags', ['bot_id'])
    op.create_index('idx_flag_reporter', 'bot_behavior_flags', ['reporter_id'])
    op.create_index('idx_flag_status', 'bot_behavior_flags', ['status'])
    op.create_index('idx_flag_type', 'bot_behavior_flags', ['flag_type'])
    op.create_index('idx_flag_created', 'bot_behavior_flags', ['created_at'])

    # ========================================================================
    # ADMIN AUDIT LOGS TABLE
    # ========================================================================
    op.create_table(
        'admin_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id'), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('details', postgresql.JSON, default={}),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_audit_admin', 'admin_audit_logs', ['admin_id'])
    op.create_index('idx_audit_action', 'admin_audit_logs', ['action'])
    op.create_index('idx_audit_entity', 'admin_audit_logs', ['entity_type', 'entity_id'])
    op.create_index('idx_audit_created', 'admin_audit_logs', ['created_at'])

    # ========================================================================
    # FLAGGED CONTENT TABLE
    # ========================================================================
    op.create_table(
        'flagged_content',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('content_type', sa.String(50), nullable=False),
        sa.Column('content_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_text', sa.Text, nullable=False),
        sa.Column('flag_reason', sa.String(100), nullable=False),
        sa.Column('flagged_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_system_flagged', sa.Boolean, default=False),
        sa.Column('status', sa.String(30), default='pending'),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime, nullable=True),
        sa.Column('action_taken', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_flagged_content_type', 'flagged_content', ['content_type'])
    op.create_index('idx_flagged_status', 'flagged_content', ['status'])
    op.create_index('idx_flagged_created', 'flagged_content', ['created_at'])

    # ========================================================================
    # SYSTEM LOGS TABLE
    # ========================================================================
    op.create_table(
        'system_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('level', sa.String(20), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('details', postgresql.JSON, default={}),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_log_level', 'system_logs', ['level'])
    op.create_index('idx_log_source', 'system_logs', ['source'])
    op.create_index('idx_log_created', 'system_logs', ['created_at'])

    # ========================================================================
    # NOTIFICATIONS TABLE
    # ========================================================================
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(30), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('data', postgresql.JSON, default={}),
        sa.Column('read', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_notification_user', 'notifications', ['user_id'])
    op.create_index('idx_notification_user_read', 'notifications', ['user_id', 'read'])
    op.create_index('idx_notification_created', 'notifications', ['created_at'])
    op.create_index('idx_notification_type', 'notifications', ['type'])

    # ========================================================================
    # PUSH SUBSCRIPTIONS TABLE
    # ========================================================================
    op.create_table(
        'push_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('endpoint', sa.Text, nullable=False, unique=True),
        sa.Column('keys', postgresql.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_push_sub_user', 'push_subscriptions', ['user_id'])
    op.create_index('idx_push_sub_endpoint', 'push_subscriptions', ['endpoint'])

    # ========================================================================
    # CONTENT REPORTS TABLE
    # ========================================================================
    op.create_table(
        'content_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('reporter_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_type', sa.String(30), nullable=False),
        sa.Column('reason', sa.String(50), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.String(30), default='pending'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolution_action', sa.String(50), nullable=True),
        sa.Column('resolution_notes', sa.Text, nullable=True),
    )
    op.create_index('idx_report_reporter', 'content_reports', ['reporter_id'])
    op.create_index('idx_report_content', 'content_reports', ['content_id'])
    op.create_index('idx_report_status', 'content_reports', ['status'])
    op.create_index('idx_report_created', 'content_reports', ['created_at'])
    op.create_index('idx_report_content_type', 'content_reports', ['content_type'])

    # ========================================================================
    # MODERATION ACTIONS TABLE
    # ========================================================================
    op.create_table(
        'moderation_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('content_reports.id'), nullable=True),
        sa.Column('moderator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('content_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_type', sa.String(30), nullable=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('automated', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_mod_action_report', 'moderation_actions', ['report_id'])
    op.create_index('idx_mod_action_moderator', 'moderation_actions', ['moderator_id'])
    op.create_index('idx_mod_action_content', 'moderation_actions', ['content_id'])
    op.create_index('idx_mod_action_created', 'moderation_actions', ['created_at'])

    # ========================================================================
    # HASHTAGS TABLE
    # ========================================================================
    op.create_table(
        'hashtags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tag', sa.String(50), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('idx_hashtag_tag', 'hashtags', ['tag'])
    op.create_index('idx_hashtag_created', 'hashtags', ['created_at'])

    # ========================================================================
    # POST HASHTAGS TABLE
    # ========================================================================
    op.create_table(
        'post_hashtags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('posts.id'), nullable=False),
        sa.Column('hashtag_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('hashtags.id'), nullable=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_unique_constraint('unique_post_hashtag', 'post_hashtags', ['post_id', 'hashtag_id'])
    op.create_index('idx_post_hashtag_post', 'post_hashtags', ['post_id'])
    op.create_index('idx_post_hashtag_hashtag', 'post_hashtags', ['hashtag_id'])
    op.create_index('idx_post_hashtag_created', 'post_hashtags', ['created_at'])

    # ========================================================================
    # HASHTAG FOLLOWS TABLE
    # ========================================================================
    op.create_table(
        'hashtag_follows',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('hashtag_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('hashtags.id'), nullable=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_unique_constraint('unique_user_hashtag_follow', 'hashtag_follows', ['user_id', 'hashtag_id'])
    op.create_index('idx_hashtag_follow_user', 'hashtag_follows', ['user_id'])
    op.create_index('idx_hashtag_follow_hashtag', 'hashtag_follows', ['hashtag_id'])
    op.create_index('idx_hashtag_follow_created', 'hashtag_follows', ['created_at'])


def downgrade() -> None:
    """Drop all database tables."""

    # Drop tables in reverse dependency order
    op.drop_table('hashtag_follows')
    op.drop_table('post_hashtags')
    op.drop_table('hashtags')
    op.drop_table('moderation_actions')
    op.drop_table('content_reports')
    op.drop_table('push_subscriptions')
    op.drop_table('notifications')
    op.drop_table('system_logs')
    op.drop_table('flagged_content')
    op.drop_table('admin_audit_logs')
    op.drop_table('bot_behavior_flags')
    op.drop_table('user_blocks')
    op.drop_table('story_views')
    op.drop_table('stories')
    op.drop_table('community_limits')
    op.drop_table('archived_memories')
    op.drop_table('retired_bots')
    op.drop_table('bot_skills')
    op.drop_table('bot_learning_states')
    op.drop_table('bot_mind_states')
    op.drop_table('system_metrics')
    op.drop_table('bot_metrics')
    op.drop_table('refresh_tokens')
    op.drop_table('app_users')
    op.drop_table('direct_messages')
    op.drop_table('community_chat_messages')
    op.drop_table('post_comments')
    op.drop_table('post_likes')
    op.drop_table('posts')
    op.drop_table('media')
    op.drop_table('daily_metrics')
    op.drop_table('user_sessions')
    op.drop_table('post_views')
    op.drop_table('generated_content')
    op.drop_table('scheduled_activities')
    op.drop_table('community_memberships')
    op.drop_table('communities')
    op.drop_table('relationships')
    op.drop_table('memory_items')
    op.drop_table('bot_profiles')

    # Drop pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
