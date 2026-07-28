"""
Story privacy tests (HIVE-010).

Two leaks, both of which defeated a promise the feature makes to its users:

    GET /stories/{id}/viewers   was anonymous, so anyone could read who had viewed
                                any story — a social-graph leak revealing who watches
                                whom. Its own docstring already said "only the story
                                author should typically have access"; no check existed.

    include_expired=true        was honoured for any caller, so anyone could retrieve
                                anyone's expired stories indefinitely. Stories are
                                ephemeral by contract; serving them forever removes the
                                only property that distinguishes them from posts.

Both now resolve to 404 rather than 403 for non-authors, so the status code does not
confirm that a story exists.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mind.api.dependencies import get_db_session
from mind.api.main import app
from mind.core.auth import create_access_token


def _token_user(user_id):
    return SimpleNamespace(
        id=user_id,
        email="user@example.com",
        display_name="Test User",
        avatar_seed=str(user_id),
        created_at=datetime(2026, 1, 1),
        is_active=True,
        is_admin=False,
        is_banned=False,
    )


@pytest.fixture
def client_as():
    def _factory(user_id=None):
        client_headers = {}
        if user_id is not None:
            result = MagicMock()
            result.scalar_one_or_none.return_value = _token_user(user_id)
            session = MagicMock()
            session.execute = AsyncMock(return_value=result)

            async def _override():
                yield session

            app.dependency_overrides[get_db_session] = _override
            client_headers["Authorization"] = f"Bearer {create_access_token(user_id)}"

        client = TestClient(app, raise_server_exceptions=False)
        client.headers.update(client_headers)
        return client

    yield _factory
    app.dependency_overrides.clear()


def _story(author_id, *, expired=False):
    return {
        "id": uuid4(),
        "author": {
            "id": author_id,
            "display_name": "Author",
            "handle": "author",
            "avatar_seed": "seed",
            "is_bot": False,
            "is_ai_labeled": False,
            "ai_label_text": "",
        },
        "content": "secret",
        "media_url": None,
        "background_color": "#000000",
        "font_style": "normal",
        "created_at": datetime(2026, 1, 1),
        "expires_at": datetime(2026, 1, 2),
        "view_count": 3,
        "is_expired": expired,
    }


@pytest.fixture
def story_service(monkeypatch):
    service = MagicMock()

    def _install(story=None, viewers=None, user_stories=None):
        service.get_story_by_id = AsyncMock(return_value=story)
        service.get_viewers = AsyncMock(return_value=viewers or [])
        service.get_user_stories = AsyncMock(return_value=user_stories or [])

        async def _get_service():
            return service

        monkeypatch.setattr(
            "mind.api.routes.stories.get_story_service", _get_service
        )
        return service

    return _install


# ============================================================================
# VIEWERS ARE AUTHOR-ONLY
# ============================================================================

def test_anonymous_cannot_read_story_viewers(client_as, story_service):
    author = uuid4()
    story_service(story=_story(author))

    response = client_as().get(f"/stories/{uuid4()}/viewers")

    assert response.status_code == 401


def test_non_author_cannot_read_story_viewers(client_as, story_service):
    author, snooper = uuid4(), uuid4()
    story_service(story=_story(author))

    response = client_as(snooper).get(f"/stories/{uuid4()}/viewers")

    assert response.status_code == 404, "a non-author read the viewer list"


def test_author_can_read_their_own_story_viewers(client_as, story_service):
    author = uuid4()
    story_service(
        story=_story(author),
        viewers=[
            {
                "viewer": {
                    "id": uuid4(),
                    "display_name": "Viewer",
                    "handle": "viewer",
                    "avatar_seed": "seed",
                    "is_bot": False,
                    "is_ai_labeled": False,
                    "ai_label_text": "",
                },
                "viewed_at": datetime(2026, 1, 1),
            }
        ],
    )

    response = client_as(author).get(f"/stories/{uuid4()}/viewers")

    assert response.status_code == 200
    assert response.json()["total"] == 1


# ============================================================================
# EXPIRED STORIES ARE AUTHOR-ONLY
# ============================================================================

def test_expired_story_is_hidden_from_anonymous_callers(client_as, story_service):
    story_service(story=_story(uuid4(), expired=True))

    response = client_as().get(f"/stories/{uuid4()}")

    assert response.status_code == 404, "an expired story was served publicly"


def test_expired_story_is_hidden_from_other_users(client_as, story_service):
    author, snooper = uuid4(), uuid4()
    story_service(story=_story(author, expired=True))

    response = client_as(snooper).get(f"/stories/{uuid4()}")

    assert response.status_code == 404


def test_author_can_still_read_their_own_expired_story(client_as, story_service):
    author = uuid4()
    story_service(story=_story(author, expired=True))

    response = client_as(author).get(f"/stories/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["is_expired"] is True


def test_live_story_remains_public(client_as, story_service):
    """The feed is deliberately public; this must not become a regression."""
    story_service(story=_story(uuid4(), expired=False))

    response = client_as().get(f"/stories/{uuid4()}")

    assert response.status_code == 200


def test_include_expired_is_ignored_for_other_users(client_as, story_service):
    """Anyone may ask; only the author is answered."""
    author, snooper = uuid4(), uuid4()
    service = story_service(user_stories=[])

    client_as(snooper).get(f"/stories/user/{author}?include_expired=true")

    service.get_user_stories.assert_awaited_once()
    assert service.get_user_stories.await_args.kwargs["include_expired"] is False


def test_include_expired_is_honoured_for_your_own_stories(client_as, story_service):
    author = uuid4()
    service = story_service(user_stories=[])

    client_as(author).get(f"/stories/user/{author}?include_expired=true")

    assert service.get_user_stories.await_args.kwargs["include_expired"] is True
