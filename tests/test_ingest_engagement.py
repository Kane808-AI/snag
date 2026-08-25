"""ingest._engagement_from tests: yt-dlp flat + TikTok nested shapes."""
import ingest


def test_engagement_flat_ytdlp_shape():
    info = {"view_count": 14200, "like_count": 634, "comment_count": 3,
            "save_count": 728, "repost_count": 192, "duration": 30}
    assert ingest._engagement_from(info) == {
        "view_count": 14200, "like_count": 634, "comment_count": 3,
        "save_count": 728, "repost_count": 192,
    }


def test_engagement_nested_tiktok_shape():
    info = {"aweme_detail": {"statistics": {"play_count": 9000, "digg_count": 500,
                                             "comment_count": 12, "collect_count": 300,
                                             "share_count": 80}}}
    eng = ingest._engagement_from(info)
    assert eng["view_count"] == 9000
    assert eng["like_count"] == 500
    assert eng["save_count"] == 300
    assert eng["repost_count"] == 80


def test_engagement_missing_returns_empty():
    assert ingest._engagement_from({"title": "no stats"}) == {}


def test_engagement_string_coerced():
    assert ingest._engagement_from({"view_count": "14200", "like_count": "634"}) == {
        "view_count": 14200, "like_count": 634,
    }
