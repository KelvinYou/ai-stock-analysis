from datetime import date

from stock_analysis.data.evidence import (
    filter_point_in_time_news,
    normalize_news_item,
)


def test_normalize_yahoo_news_keeps_publication_provenance():
    item = normalize_news_item(
        {
            "content": {
                "title": "Earnings update",
                "pubDate": "2026-09-01T12:30:00Z",
                "provider": {"displayName": "Example Wire"},
                "canonicalUrl": {"url": "https://example.test/story"},
            }
        }
    )

    assert item == {
        "title": "Earnings update",
        "link": "https://example.test/story",
        "publisher": "Example Wire",
        "published_at": "2026-09-01T12:30:00+00:00",
    }


def test_point_in_time_news_rejects_future_and_undated_items():
    kept = filter_point_in_time_news(
        [
            {
                "title": "Known",
                "published_at": "2026-09-01T00:00:00Z",
                "available_as_of": "2026-09-01",
            },
            {
                "title": "Future publication",
                "published_at": "2026-09-03T00:00:00Z",
            },
            {"title": "No timestamp"},
        ],
        as_of=date(2026, 9, 2),
    )

    assert [item["title"] for item in kept] == ["Known"]


def test_replay_requires_explicit_first_available_date():
    records = [
        {
            "title": "No embargo metadata",
            "published_at": "2026-09-01T00:00:00Z",
        },
        {
            "title": "Embargoed until later",
            "published_at": "2026-09-01T00:00:00Z",
            "available_as_of": "2026-09-03",
        },
        {
            "title": "Replay-safe",
            "published_at": "2026-09-01T00:00:00Z",
            "available_as_of": "2026-09-01",
        },
    ]

    kept = filter_point_in_time_news(
        records,
        as_of=date(2026, 9, 2),
        require_embargo=True,
    )

    assert [item["title"] for item in kept] == ["Replay-safe"]
