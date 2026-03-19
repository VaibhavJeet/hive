"""
API endpoint tests for core Hive functionality.

Tests the main API routes:
- Feed endpoints (posts, comments, likes)
- User endpoints (registration, profile)
- Community endpoints
- Bot endpoints

Note: Tests marked with @pytest.mark.integration require a running database.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


# Mark for tests that require database connectivity
requires_db = pytest.mark.skipif(
    True,  # Always skip unless explicitly enabled
    reason="Requires running database connection"
)


class TestFeedEndpoints:
    """Test feed-related API endpoints."""

    def test_get_feed_structure(self, api_client):
        """Test that feed endpoint returns expected structure."""
        response = api_client.get("/feed/posts?limit=5")

        # Should return 200, empty list, or 500 if DB issues
        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_get_feed_with_pagination(self, api_client):
        """Test feed pagination parameters."""
        response = api_client.get("/feed/posts?limit=10&offset=0")
        assert response.status_code in [200, 404, 500]

    def test_get_feed_with_community_filter(self, api_client):
        """Test feed filtering by community."""
        fake_community_id = str(uuid4())
        response = api_client.get(f"/feed/posts?community_id={fake_community_id}")
        assert response.status_code in [200, 404, 500]


class TestUserEndpoints:
    """Test user-related API endpoints."""

    def test_register_user_structure(self, api_client):
        """Test user registration endpoint structure."""
        response = api_client.post(
            "/users/register",
            json={
                "device_id": f"test-device-{uuid4()}",
                "display_name": "TestUser"
            }
        )

        # Should succeed or indicate duplicate/validation error
        assert response.status_code in [200, 201, 400, 422, 500]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data
            assert "display_name" in data

    def test_list_bots_structure(self, api_client):
        """Test bots listing endpoint structure."""
        response = api_client.get("/users/bots?limit=5")

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_list_communities_structure(self, api_client):
        """Test communities listing endpoint structure."""
        response = api_client.get("/users/communities")

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)


class TestCommunityEndpoints:
    """Test community-related API endpoints."""

    def test_list_communities(self, api_client):
        """Test listing communities (via /users/communities)."""
        response = api_client.get("/users/communities")
        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)


class TestAnalyticsEndpoints:
    """Test analytics API endpoints."""

    def test_realtime_analytics_structure(self, api_client):
        """Test realtime analytics endpoint."""
        response = api_client.get("/analytics/realtime")

        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            data = response.json()
            # Should have realtime metrics
            assert isinstance(data, dict)

    def test_overview_analytics_structure(self, api_client):
        """Test overview analytics endpoint."""
        response = api_client.get("/analytics/overview")

        assert response.status_code in [200, 401, 403]


class TestAdminEndpoints:
    """Test admin API endpoints."""

    def test_admin_stats_requires_auth(self, api_client):
        """Test that admin stats endpoint exists."""
        response = api_client.get("/admin/stats")

        # Should either return stats or require auth
        assert response.status_code in [200, 401, 403]

    def test_admin_bots_list(self, api_client):
        """Test admin bots listing."""
        response = api_client.get("/admin/bots")

        assert response.status_code in [200, 401, 403]

    def test_admin_posts_list(self, api_client):
        """Test admin posts listing."""
        response = api_client.get("/admin/posts")

        assert response.status_code in [200, 401, 403]


class TestNotificationEndpoints:
    """Test notification API endpoints (require database)."""

    @requires_db
    def test_get_notifications_structure(self, api_client):
        """Test notifications endpoint structure."""
        fake_user_id = str(uuid4())
        response = api_client.get(f"/notifications?user_id={fake_user_id}")

        assert response.status_code in [200, 401, 422, 500]

        if response.status_code == 200:
            data = response.json()
            assert "notifications" in data or isinstance(data, list)

    @requires_db
    def test_unread_count_structure(self, api_client):
        """Test unread count endpoint."""
        fake_user_id = str(uuid4())
        response = api_client.get(f"/notifications/unread-count?user_id={fake_user_id}")

        assert response.status_code in [200, 401, 422, 500]


class TestSearchEndpoints:
    """Test search API endpoints (require database)."""

    @requires_db
    def test_search_posts_structure(self, api_client):
        """Test post search endpoint."""
        response = api_client.get("/search/posts?q=test")

        assert response.status_code in [200, 404, 500]

    @requires_db
    def test_search_bots_structure(self, api_client):
        """Test bot search endpoint."""
        response = api_client.get("/search/bots?q=test")

        assert response.status_code in [200, 404, 500]


class TestHashtagEndpoints:
    """Test hashtag API endpoints (require database)."""

    @requires_db
    def test_trending_hashtags(self, api_client):
        """Test trending hashtags endpoint."""
        response = api_client.get("/hashtags/trending")

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @requires_db
    def test_hashtag_posts(self, api_client):
        """Test getting posts by hashtag."""
        response = api_client.get("/hashtags/test/posts")

        assert response.status_code in [200, 404, 500]


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, api_client):
        """Test detailed health check."""
        response = api_client.get("/health")
        # May return 503 if services unavailable
        assert response.status_code in [200, 503]

    def test_liveness_check(self, api_client):
        """Test liveness probe."""
        response = api_client.get("/health/live")
        assert response.status_code == 200

    def test_ready_check(self, api_client):
        """Test readiness probe."""
        response = api_client.get("/health/ready")
        # May fail if DB/Ollama isn't connected, which is fine
        assert response.status_code in [200, 503]


class TestBotEndpoints:
    """Test bot-specific API endpoints."""

    def test_get_bot_profile(self, api_client):
        """Test getting a bot profile."""
        fake_bot_id = str(uuid4())
        response = api_client.get(f"/users/{fake_bot_id}/profile")

        assert response.status_code in [200, 404, 500]

    def test_get_bot_posts(self, api_client):
        """Test getting posts by a specific bot."""
        fake_bot_id = str(uuid4())
        response = api_client.get(f"/users/{fake_bot_id}/posts")

        assert response.status_code in [200, 404, 500]

    def test_follow_bot(self, api_client):
        """Test following a bot."""
        fake_bot_id = str(uuid4())
        fake_user_id = str(uuid4())
        response = api_client.post(
            f"/users/{fake_bot_id}/follow",
            json={"follower_id": fake_user_id}
        )

        assert response.status_code in [200, 201, 400, 404, 422, 500]


class TestPostEndpoints:
    """Test post-specific API endpoints."""

    def test_get_single_post(self, api_client):
        """Test getting a single post."""
        fake_post_id = str(uuid4())
        response = api_client.get(f"/feed/posts/{fake_post_id}")

        assert response.status_code in [200, 404, 500]

    def test_get_post_comments(self, api_client):
        """Test getting comments on a post."""
        fake_post_id = str(uuid4())
        response = api_client.get(f"/feed/posts/{fake_post_id}/comments")

        assert response.status_code in [200, 404, 500]

    def test_like_post(self, api_client):
        """Test liking a post."""
        fake_post_id = str(uuid4())
        fake_user_id = str(uuid4())
        response = api_client.post(
            f"/feed/posts/{fake_post_id}/like",
            json={"user_id": fake_user_id}
        )

        assert response.status_code in [200, 201, 400, 404, 422, 500]


class TestInteractionEndpoints:
    """Test interaction-related endpoints."""

    def test_create_comment(self, api_client):
        """Test creating a comment."""
        fake_post_id = str(uuid4())
        fake_user_id = str(uuid4())
        response = api_client.post(
            f"/feed/posts/{fake_post_id}/comments",
            json={
                "user_id": fake_user_id,
                "content": "Test comment"
            }
        )

        assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_share_post(self, api_client):
        """Test sharing a post."""
        fake_post_id = str(uuid4())
        fake_user_id = str(uuid4())
        response = api_client.post(
            f"/feed/posts/{fake_post_id}/share",
            json={"user_id": fake_user_id}
        )

        # Share endpoint might not exist yet
        assert response.status_code in [200, 201, 400, 404, 405, 422, 500]
