"""
Search hardening tests (HIVE-016).

Two problems, one of which was not in the task description.

**Search was anonymous.** Full-text search is the most expensive read in the API, and
until `search_vector` is populated (HIVE-139) every query is a sequential scan that
computes `to_tsvector` per row. Requiring a session bounds who can spend that and gives
the rate limiter something to attribute it to.

**`_prepare_query` did not sanitise anything.** Its docstring said "Remove special
characters that could break tsquery"; it split on whitespace and appended `:*`. So
`foo!` became `foo!:*`, `to_tsquery` raised a syntax error, and any search containing
punctuation returned 500. Not a SQL injection — the value is bound — but user input was
being parsed as tsquery *grammar*.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mind.api.main import app
from mind.search.search_service import SearchService

SEARCH_ENDPOINTS = [
    "/search?q=test",
    "/search/posts?q=test",
    "/search/suggestions?q=test",
    "/search/users?q=test",
    "/search/bots?q=test",
    "/hashtags/search/query?q=test",
]


@pytest.fixture
def service():
    return SearchService()


# ============================================================================
# Search requires a session
# ============================================================================

@pytest.mark.parametrize("path", SEARCH_ENDPOINTS)
def test_search_rejects_anonymous_callers(path):
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get(path).status_code == 401, f"GET {path} was anonymous"


@pytest.mark.parametrize("path", ["/hashtags/trending", f"/hashtags/python/posts"])
def test_hashtag_browsing_stays_public(path):
    """Trending and tag feeds are browse surfaces, not search."""
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get(path).status_code != 401, f"GET {path} now requires auth"


# ============================================================================
# Query preparation cannot produce an invalid tsquery
# ============================================================================

@pytest.mark.parametrize(
    "query",
    ["foo!", "a & b", "a | b", "!negated", "((", "))", "a:b", "*", "'quoted'",
     '"double"', "back\\slash", "<->", "; DROP TABLE posts; --", "%", "^", "~"],
)
def test_operators_never_reach_the_parser(service, query):
    prepared = service._prepare_query(query)
    for char in "&|!()<>:*'\"\\":
        stray = prepared.replace(":*", "").replace(" & ", " ")
        assert char not in stray, (
            f"{char!r} survived sanitisation of {query!r} -> {prepared!r}"
        )


@pytest.mark.parametrize("query", ["((", "))", "!!!", "-- --", "", "   ", "&|!"])
def test_queries_with_nothing_searchable_return_empty(service, query):
    assert service._prepare_query(query) == ""


def test_ordinary_queries_still_work(service):
    assert service._prepare_query("hello world") == "hello:* & world:*"


def test_hyphenated_words_survive(service):
    """`-` is deliberately allowed; it is not a tsquery operator."""
    assert service._prepare_query("cafe-noir") == "cafe-noir:*"


def test_term_count_is_capped(service):
    """Each term is another AND clause evaluated per row while the index is unused."""
    prepared = service._prepare_query(" ".join(f"w{i}" for i in range(200)))
    assert prepared.count("&") == 9, "expected 10 terms max"


def test_unicode_words_are_preserved(service):
    assert service._prepare_query("naïve") == "naïve:*"


def test_docstring_promise_is_now_true(service):
    """The original docstring claimed sanitisation that did not happen (HIVE-010's
    lesson: a docstring is not evidence). This asserts the behaviour, not the prose."""
    assert service._prepare_query("foo!") == "foo:*"
