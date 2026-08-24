"""bot.py tests: commands, callbacks, the save flow, and the duration gate.

The Telegram API is stubbed (fake_api) so nothing ever touches the live
service. Analysis, transcription, and billing are stubbed too.

Note: send()/edit() convert `**bold**` and `code` markers to HTML before the
stub sees the text, so assertions match the HTML form (<b>, <code>).
"""
import pytest

import db
import bot
from conftest import make_item, msg, cb


TIKTOK = "https://www.tiktok.com/t/ZTD5K5MKb"


@pytest.fixture
def stub_analysis(monkeypatch):
    """Deterministic note + triage + transcription, no network."""
    note = {"summary": "AI tools for marketers", "key_ideas": "build in public",
            "why_it_matters": "matters for Brand75", "recommendations": "ship one tool",
            "tags": ["ai-tools", "marketing"], "raw": "raw"}
    triage = {"stage": "Worth Acting On", "action_type": "Make content",
              "impact": 4, "effort": 2}
    monkeypatch.setattr(bot.analyze, "analyze_note", lambda t: dict(note))
    monkeypatch.setattr(bot.analyze, "analyze_triage", lambda n: dict(triage))
    monkeypatch.setattr(bot.ingest, "transcript_from_url",
                        lambda url: (True, "transcript of the video", ""))
    monkeypatch.setattr(bot.ingest, "probe_duration", lambda url: None)
    return note, triage


def sent(fake, method="sendMessage"):
    return [c for c in fake.calls if c[0] == method]


def edited(fake):
    return [c for c in fake.calls if c[0] == "editMessageText"]


def last_send_text(fake):
    return sent(fake)[-1][1]["text"]


def last_sent_msg_id(fake):
    """Telegram-assigned message_id of the most recent sendMessage."""
    for m, _p, r in reversed(fake.calls):
        if m == "sendMessage":
            return r["result"]["message_id"]
    return None


def markup_flat(params):
    return [b["callback_data"] for row in params["reply_markup"]["inline_keyboard"] for b in row]


# --- F1: save flow with immediate feedback, resolves into the card -----------

def test_link_flow_processing_then_card(fresh_db, fake_api, stub_analysis, no_billing, pump):
    bot.handle_message(msg(TIKTOK))
    # 1. immediate processing message before any analysis
    assert fake_api.calls[0][0] == "sendMessage"
    assert "working on it" in fake_api.calls[0][1]["text"]
    # 2. the worker resolves the ack into the card by editing that same message
    assert pump() == 1
    assert edited(fake_api), "card must edit the processing message"
    card = edited(fake_api)[-1][1]
    assert card["message_id"] == 1001
    assert markup_flat(card)[:2] == ["save", "discard"]
    assert "Worth Acting On" in card["text"] and "Make content" in card["text"]
    assert "Impact 4/5 · Effort 2/5" in card["text"]
    assert "9 free captures left" in card["text"]


def test_save_callback_stores_and_resolves_card(fresh_db, fake_api, stub_analysis, no_billing, pump):
    bot.handle_message(msg(TIKTOK))
    pump()
    bot.handle_callback(cb("save", 1001))
    item = db.get_vault_item(1, 1)
    assert item and item["summary"] == "AI tools for marketers"
    assert item["status"] == "inbox" and item["stage"] == "Worth Acting On"
    assert item["tags"] == "ai-tools,marketing"
    card = edited(fake_api)[-1][1]
    assert "<code>#1</code>" in card["text"] and "📥 inbox" in card["text"]
    flat = markup_flat(card)
    assert "open:1" in flat and "regen:1" in flat and "delete:1" in flat
    assert "save" not in flat and "discard" not in flat
    assert any(p.get("text") == "Saved as #1"
               for m, p, _r in fake_api.calls if m == "answerCallbackQuery")


def test_discard_callback_does_not_save(fresh_db, fake_api, stub_analysis, no_billing, pump):
    bot.handle_message(msg(TIKTOK))
    pump()
    bot.handle_callback(cb("discard", 1001))
    assert db.list_vault(1) == []
    assert "Discarded" in edited(fake_api)[-1][1]["text"]


def test_save_expired_pending(fresh_db, fake_api, stub_analysis, no_billing):
    # no pending item for this message id (simulates a bot restart)
    bot.handle_callback(cb("save", 9999))
    assert "expired" in edited(fake_api)[-1][1]["text"]


def test_open_pending_and_saved(fresh_db, fake_api, stub_analysis, no_billing, pump):
    bot.handle_message(msg(TIKTOK))
    pump()
    bot.handle_callback(cb("open", 1001))
    assert last_send_text(fake_api) == TIKTOK
    bot.handle_callback(cb("save", 1001))
    bot.handle_callback(cb("open:1", 1001))
    assert last_send_text(fake_api) == TIKTOK


# --- F2: item card buttons ---------------------------------------------------

def test_saved_card_has_full_button_set(fresh_db, fake_api, no_billing):
    vid = make_item(1, "saved idea", stage="Worth Acting On", at="Make content",
                    impact=4, effort=2, tags="x,y")
    bot.handle_message(msg(f"/status {vid}"))  # cycles inbox -> in progress, renders card
    card = last_send_text(fake_api)
    assert "<b>saved idea</b>" in card
    assert "🔄 in progress" in card
    flat = markup_flat(sent(fake_api)[-1][1])
    assert set(flat) == {"open:1", "transcript:1", "tag:1", "status:1",
                         "regen:1", "share:1", "delete:1"}


# --- F3: transcript view -----------------------------------------------------

def test_transcript_command_and_copyfile(fresh_db, fake_api, no_billing, monkeypatch):
    vid = make_item(1, "t item", transcript="the full transcript text here")
    bot.handle_message(msg(f"/transcript {vid}"))
    text = last_send_text(fake_api)
    assert "<b>Transcript #1</b>" in text and "the full transcript text here" in text
    assert markup_flat(sent(fake_api)[-1][1]) == ["copyfile:1"]
    uploads = []
    monkeypatch.setattr(bot, "_post_upload",
                        lambda url, body, headers: uploads.append((url, body)) or {"ok": True})
    bot.handle_callback(cb("copyfile:1", 42))
    assert uploads and "snag-1-transcript.txt" in uploads[0][1].decode("latin-1")


# --- F4: vault list with chips and pagination --------------------------------

def test_vault_command_renders_rows_and_chips(fresh_db, fake_api, no_billing):
    make_item(1, "actionable idea", stage="Worth Acting On", impact=4, effort=2)
    make_item(1, "reference idea", stage="Reference")
    bot.handle_message(msg("/vault"))
    text = last_send_text(fake_api)
    assert "<b>Your vault</b> (2 saved)" in text
    assert "<code>#2</code> [Reference] [📥 inbox]" in text
    assert "<code>#1</code> [Worth Acting On] [📥 inbox] ⚡4/2" in text
    flat = markup_flat(sent(fake_api)[-1][1])
    assert "vault:0:all" in flat and "vault:0:inbox" in flat and "vault:0:ref" in flat


def test_vault_pagination_and_filter_callback(fresh_db, fake_api, no_billing):
    for i in range(25):
        make_item(1, f"idea {i}")
    make_item(1, "act one", stage="Worth Acting On")
    make_item(1, "act two", stage="Worth Acting On")
    bot.handle_message(msg("/vault"))
    text = last_send_text(fake_api)
    assert "Page 1 of 2" in text and "idea 24" in text
    list_msg_id = last_sent_msg_id(fake_api)
    bot.handle_callback(cb("vault:1:all", list_msg_id))
    page2 = edited(fake_api)[-1][1]
    assert "Page 2 of 2" in page2["text"] and "idea 4" in page2["text"]
    bot.handle_callback(cb("vault:0:act", list_msg_id))
    assert "filtered by" in edited(fake_api)[-1][1]["text"]
    bot.handle_message(msg("/vault act"))
    assert "filtered by" in last_send_text(fake_api)


def test_vault_empty(fresh_db, fake_api, no_billing):
    bot.handle_message(msg("/vault"))
    assert "empty" in last_send_text(fake_api)


# --- F5: search with filters -------------------------------------------------

def test_search_command_with_filters(fresh_db, fake_api, no_billing):
    make_item(1, "build an ai tool", stage="Worth Acting On", at="Build a tool",
              impact=4, effort=2, tags="github,ai-tools")
    make_item(1, "crm notes", stage="Reference", tags="crm")
    bot.handle_message(msg("/search build stage:act tag:ai-tools impact:4"))
    text = last_send_text(fake_api)
    assert "Matches for" in text and "build an ai tool" in text
    assert "crm notes" not in text
    bot.handle_message(msg("/search stage:reference"))
    assert "crm notes" in last_send_text(fake_api)
    bot.handle_message(msg("/search zzzznope"))
    assert "No saved ideas match" in last_send_text(fake_api)
    bot.handle_message(msg("/search"))
    assert "Usage:" in last_send_text(fake_api)


# --- F6: actions queue -------------------------------------------------------

def test_actions_command_sorted_with_buttons(fresh_db, fake_api, no_billing):
    make_item(1, "low impact", stage="Worth Acting On", impact=2, effort=5)
    make_item(1, "high impact", stage="Worth Acting On", at="Make content", impact=5, effort=1)
    make_item(1, "reference", stage="Reference")
    bot.handle_message(msg("/actions"))
    text = last_send_text(fake_api)
    assert text.index("high impact") < text.index("low impact")
    flat = markup_flat(sent(fake_api)[-1][1])
    assert "action_done:2" in flat and "action_later:2" in flat and "action_snooze:2" in flat
    actions_msg = last_sent_msg_id(fake_api)
    bot.handle_callback(cb("action_done:2", actions_msg))
    assert "high impact" not in edited(fake_api)[-1][1]["text"]
    assert any(p.get("text") == "Done, nice work."
               for m, p, _r in fake_api.calls if m == "answerCallbackQuery")
    bot.handle_callback(cb("action_later:1", 55))
    assert db.get_vault_item(1, 1)["stage"] == "Reference"
    bot.handle_callback(cb("action_snooze:2", 56))
    assert db.get_vault_item(1, 2)["snooze_until"] is not None


def test_actions_empty(fresh_db, fake_api, no_billing):
    bot.handle_message(msg("/actions"))
    assert "All clear" in last_send_text(fake_api)


# --- F7: tag editing ---------------------------------------------------------

def test_tag_command_add_remove(fresh_db, fake_api, no_billing):
    vid = make_item(1, "tag me", tags="auto-one")
    make_item(1, "other", tags="suggestion-tag")
    bot.handle_message(msg(f"/tag {vid}"))
    text = last_send_text(fake_api)
    assert "<b>Tags for #1</b>" in text and "auto-one" in text
    flat = markup_flat(sent(fake_api)[-1][1])
    assert "tagadd:1:suggestion-tag" in flat and "tagdel:1:auto-one" in flat
    bot.handle_message(msg(f"/tag {vid} add user-tag"))
    assert "Added to #1" in last_send_text(fake_api)
    assert db.get_tags(1, vid) == ["auto-one", "user-tag"]
    bot.handle_message(msg(f"/tag {vid} remove auto-one"))
    assert db.get_tags(1, vid) == ["user-tag"]


def test_tag_callbacks_edit_in_place(fresh_db, fake_api, no_billing):
    vid = make_item(1, "tagged", tags="a")
    bot.handle_message(msg(f"/tag {vid}"))
    editor_msg = last_sent_msg_id(fake_api)
    bot.handle_callback(cb(f"tagadd:{vid}:newword", editor_msg))
    assert db.get_tags(1, vid) == ["a", "newword"]
    assert "newword" in edited(fake_api)[-1][1]["text"]
    bot.handle_callback(cb(f"tagdone:{vid}", editor_msg))
    card = edited(fake_api)[-1][1]
    assert "<b>tagged</b>" in card["text"] and "<b>Key Ideas</b>" in card["text"]


# --- F8: status lifecycle ----------------------------------------------------

def test_status_command_and_callback_cycle(fresh_db, fake_api, no_billing):
    vid = make_item(1, "status me")
    bot.handle_message(msg(f"/status {vid}"))
    assert db.get_vault_item(1, vid)["status"] == "in progress"
    assert "🔄 in progress" in last_send_text(fake_api)
    bot.handle_message(msg(f"/status {vid} done"))
    assert db.get_vault_item(1, vid)["status"] == "done"
    bot.handle_message(msg(f"/status {vid} bogus"))
    assert "Status must be one of" in last_send_text(fake_api)
    bot.handle_callback(cb(f"status:{vid}", 77))
    assert db.get_vault_item(1, vid)["status"] == "archived"
    bot.handle_callback(cb(f"status:{vid}", 78))
    assert db.get_vault_item(1, vid)["status"] == "inbox"


# --- F9 / F10: regenerate and share ------------------------------------------

def test_regen_callback_reruns_analysis(fresh_db, fake_api, no_billing, monkeypatch):
    vid = make_item(1, "old summary", transcript="stored transcript")
    new_note = {"summary": "fresh summary", "key_ideas": "fresh ideas",
                "why_it_matters": "fresh why", "recommendations": "fresh recs",
                "tags": ["new-tag"], "raw": "r"}
    monkeypatch.setattr(bot.analyze, "analyze_note", lambda t: dict(new_note))
    bot.handle_callback(cb(f"regen:{vid}", 90))
    assert db.get_vault_item(1, vid)["summary"] == "fresh summary"
    assert db.get_vault_item(1, vid)["tags"] == "new-tag"
    assert "fresh summary" in edited(fake_api)[-1][1]["text"]


def test_share_command_and_callback(fresh_db, fake_api, no_billing):
    vid = make_item(1, "share me", tags="a,b", source_url="https://tiktok.com/v/1")
    bot.handle_message(msg(f"/share {vid}"))
    text = last_send_text(fake_api)
    assert "<b>share me</b>" in text and "<b>Key Ideas</b>" in text
    assert "Source: https://tiktok.com/v/1" in text
    bot.handle_callback(cb(f"share:{vid}", 91))
    assert "Source: https://tiktok.com/v/1" in last_send_text(fake_api)


# --- delete ------------------------------------------------------------------

def test_delete_command_and_callback(fresh_db, fake_api, no_billing):
    vid = make_item(1, "doomed")
    bot.handle_message(msg(f"/delete {vid}"))
    assert db.get_vault_item(1, vid) is None
    assert "🗑 Deleted #1." in last_send_text(fake_api)
    vid2 = make_item(1, "doomed 2")
    bot.handle_callback(cb(f"delete:{vid2}", 92))
    assert db.get_vault_item(1, vid2) is None
    assert "🗑 Deleted" in edited(fake_api)[-1][1]["text"]


# --- F11: plan ---------------------------------------------------------------

def test_plan_free_and_pro(fresh_db, fake_api, no_billing):
    bot.handle_message(msg("/plan"))
    text = last_send_text(fake_api)
    assert "<b>Plan</b>: Free" in text
    assert f"Captures this month: 0 of {db.config.FREE_MONTHLY_LIMIT}" in text
    assert f"Captures left: {db.config.FREE_MONTHLY_LIMIT}" in text
    assert "Upgrade for unlimited captures" in text
    db.set_plan(1, "pro")
    bot.handle_message(msg("/plan"))
    text = last_send_text(fake_api)
    assert "<b>Plan</b>: Pro" in text and "unlimited" in text


def test_plan_upgrade_button(fresh_db, fake_api, no_billing, monkeypatch):
    monkeypatch.setattr(bot.billing, "create_checkout_link", lambda uid: "https://checkout.test")
    bot.handle_message(msg("/plan"))
    last = sent(fake_api)[-1][1]
    assert last["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://checkout.test"


# --- F12: duration gate ------------------------------------------------------

def test_link_duration_gate_rejects_long_video(fresh_db, fake_api, stub_analysis,
                                               no_billing, monkeypatch, pump):
    monkeypatch.setattr(bot.ingest, "probe_duration", lambda url: 9999)
    monkeypatch.setattr(bot.ingest, "transcript_from_url",
                        lambda url: (_ for _ in ()).throw(AssertionError("must not transcribe")))
    bot.handle_message(msg(TIKTOK))
    # processing message first, then the worker edits it with the rejection
    assert "working on it" in fake_api.calls[0][1]["text"]
    pump()
    rejection = edited(fake_api)[-1][1]
    assert "<b>9999 seconds</b>" in rejection["text"]
    assert "free plan covers videos up to" in rejection["text"]
    assert db.list_vault(1) == []


def test_link_short_video_passes_gate(fresh_db, fake_api, stub_analysis, no_billing,
                                      monkeypatch, pump):
    monkeypatch.setattr(bot.ingest, "probe_duration", lambda url: 60)
    bot.handle_message(msg(TIKTOK))
    pump()
    assert any(m == "editMessageText" for m, _p, _r in fake_api.calls)  # card arrived


def test_link_pro_user_skips_duration_gate(fresh_db, fake_api, stub_analysis, no_billing,
                                           monkeypatch, pump):
    db.upsert_user(1, "tester")
    db.set_plan(1, "pro")
    probe_calls = []
    monkeypatch.setattr(bot.ingest, "probe_duration",
                        lambda url: probe_calls.append(url) or 9999)
    bot.handle_message(msg(TIKTOK))
    assert probe_calls == []  # nothing probed at receipt
    pump()
    assert probe_calls == []  # pro user skips the gate in the worker too
    assert any(m == "editMessageText" for m, _p, _r in fake_api.calls)


def test_file_duration_gate_rejects(fresh_db, fake_api, no_billing, monkeypatch):
    monkeypatch.setattr(bot.ingest, "probe_file_duration", lambda path: 500)
    monkeypatch.setattr(bot.analyze, "transcribe_local",
                        lambda path: (_ for _ in ()).throw(AssertionError("must not transcribe")))
    bot._process_file(1, 1, "/tmp/fake.mp4", "uploaded-file", 1001)
    rejection = edited(fake_api)[-1][1]
    assert "<b>500 seconds</b>" in rejection["text"]


# --- misc --------------------------------------------------------------------

def test_unknown_command_help(fresh_db, fake_api, no_billing):
    bot.handle_message(msg("/nonsense"))
    assert "Send me any link" in last_send_text(fake_api)


def test_start_welcome(fresh_db, fake_api, no_billing):
    bot.handle_message(msg("/start"))
    assert "Welcome to" in last_send_text(fake_api)
    assert "/actions" in last_send_text(fake_api)


# --- capture any URL: text path (articles, web pages, posts) -----------------

ARTICLE_URL = "https://example.com/some-article"


def test_text_url_flow_produces_card(fresh_db, fake_api, stub_analysis, no_billing,
                                     monkeypatch, pump):
    monkeypatch.setattr(bot.ingest, "is_video_url", lambda url: False)
    monkeypatch.setattr(bot.ingest, "fetch_text",
                        lambda url: (True, "article body text", ""))
    # a probe_duration call on a text URL would be wrong; make it fail loudly
    monkeypatch.setattr(bot.ingest, "probe_duration",
                        lambda url: (_ for _ in ()).throw(AssertionError("no video probe for text")))
    bot.handle_message(msg(ARTICLE_URL))
    assert "working on it" in fake_api.calls[0][1]["text"]
    assert pump() == 1
    card = edited(fake_api)[-1][1]
    assert "AI tools for marketers" in card["text"]  # stub note summary
    assert "Worth Acting On" in card["text"]


def test_text_url_save_stores_article_content_type(fresh_db, fake_api, stub_analysis,
                                                   no_billing, monkeypatch, pump):
    monkeypatch.setattr(bot.ingest, "is_video_url", lambda url: False)
    monkeypatch.setattr(bot.ingest, "fetch_text",
                        lambda url: (True, "article body text", ""))
    bot.handle_message(msg(ARTICLE_URL))
    pump()
    bot.handle_callback(cb("save", 1001))
    item = db.get_vault_item(1, 1)
    assert item and item["content_type"] == "article"
    assert item["summary"] == "AI tools for marketers"


def test_text_url_fetch_failure_is_friendly(fresh_db, fake_api, no_billing,
                                            monkeypatch, pump):
    monkeypatch.setattr(bot.ingest, "is_video_url", lambda url: False)
    monkeypatch.setattr(bot.ingest, "fetch_text",
                        lambda url: (False, "", "connection refused"))
    bot.handle_message(msg(ARTICLE_URL))
    assert pump() == 1
    rejection = edited(fake_api)[-1][1]
    assert "couldn't read that page" in rejection["text"]
    assert db.list_vault(1) == []
