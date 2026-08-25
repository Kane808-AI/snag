"""Tests for YouTube native-caption ingestion (ingest.is_youtube, _clean_vtt)."""

import ingest

SAMPLE_VTT = (
    "WEBVTT\n"
    "Kind: captions\n"
    "Language: en\n"
    "\n"
    "00:00:00.000 --> 00:00:01.000 align:start position:0%\n"
    "So<00:00:00.200><c> you</c><00:00:00.400><c> think</c>\n"
    "\n"
    "00:00:01.000 --> 00:00:01.010 align:start position:0%\n"
    "So you think\n"
    "\n"
    "00:00:01.010 --> 00:00:02.000 align:start position:0%\n"
    "So you think\n"
    "on<00:00:01.500><c> Etsy</c>\n"
    "\n"
    "00:00:02.000 --> 00:00:02.010 align:start position:0%\n"
    "on Etsy\n"
)


def test_is_youtube_true_cases():
    assert ingest.is_youtube("https://www.youtube.com/watch?v=abc123")
    assert ingest.is_youtube("https://youtu.be/abc123?si=xyz")
    assert ingest.is_youtube("https://m.youtube.com/watch?v=abc123")


def test_is_youtube_false_cases():
    assert not ingest.is_youtube("https://www.youtube.com.evil.com/watch?v=x")
    assert not ingest.is_youtube("https://notyoutube.com/watch?v=x")
    assert not ingest.is_youtube("https://www.tiktok.com/t/xyz")
    assert not ingest.is_youtube("https://www.instagram.com/reel/xyz/")


def test_clean_vtt_strips_timing_and_word_tags():
    assert ingest._clean_vtt(SAMPLE_VTT) == "So you think on Etsy"


def test_clean_vtt_empty():
    assert ingest._clean_vtt("WEBVTT\n\n") == ""
    assert ingest._clean_vtt("") == ""
