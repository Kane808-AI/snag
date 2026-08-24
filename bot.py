"""
Snag Telegram bot (Hermes build). Long-polling, stdlib only.

User flow:
  /start                  -> register + welcome
  send a TikTok link      -> instant ack -> item card with triage badges
                             and Save/Discard, Open, Transcript buttons
  send a TikTok video file-> local whisper -> same card
  💾 Save                 -> vault, card resolves to the saved item card
  /vault                  -> recent items with status + triage badges, stage
                             filter chips, pagination
  /search <q> [stage:x tag:x impact:x] -> FTS5 search with filters
  /actions                -> the Actions queue: Worth Acting On sorted by
                             impact over effort, Done / Later / Snooze per row
  /tag <id> [add|remove]  -> edit tags, autocomplete from existing tags
  /transcript <id>        -> full transcript with a copy-to-file button
  /regen <id>             -> rerun the AI note on the stored transcript
  /share <id>             -> the note as clean text for forwarding
  /status <id> [status]   -> inbox -> in progress -> done -> archived
  /plan                   -> quota, plan state, upgrade path
  /upgrade                -> Stripe checkout link
  quota hit or too-long video (free plan) -> friendly rejection

Pipeline is async: a link or file is acknowledged instantly and queued in the
SQLite jobs table, then an in-process worker thread (worker.py) runs
ingest -> analyze_note -> analyze_triage and resolves the ack into the card.
Long videos no longer stall the polling loop.

Run: python3 bot.py
"""
import html as _html
import json
import re as _re
import time
import urllib.request
import urllib.parse
import uuid
from pathlib import Path

import config
import db
import ingest
import analyze
import billing
import worker

API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}"

# pending (unsaved) item cards, keyed by (chat_id, message_id) so each card's
# Save/Discard buttons act on the right item even with several in flight
_PENDING = {}

_RECENT_CB = {}  # (chat_id, data) -> ts; debounce double-taps

_STATUS_ICON = {
    "inbox": "📥",
    "in progress": "🔄",
    "done": "✅",
    "archived": "🗄️",
}

_STAGE_KEY = {
    "all": None,
    "inbox": "Inbox",
    "ref": "Reference",
    "act": "Worth Acting On",
}


def _api(method, **params):
    url = f"{API}/{method}"
    data = urllib.parse.urlencode(
        {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in params.items()}
    ).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=70) as r:
        return json.loads(r.read().decode())


def _post_upload(url, body, headers):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=70) as r:
        return json.loads(r.read().decode())


def send_document(chat_id, filename, content, caption=""):
    """Send a text document (multipart). Used by the transcript copy button."""
    boundary = f"----Snag{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
    ).encode()
    if caption:
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
        ).encode()
    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
    ).encode()
    body += content.encode("utf-8")
    body += f"\r\n--{boundary}--\r\n".encode()
    try:
        return _post_upload(
            f"{API}/sendDocument",
            body,
            {"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
    except Exception as e:
        print("sendDocument failed:", repr(e), flush=True)
        return None


def _chunks(text, size=3900):
    """Split on line boundaries to stay under Telegram's 4096-char message limit."""
    parts = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut <= 0:
            cut = size
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    parts.append(text)
    return parts


def _to_html(text):
    """Escape everything, then convert our **bold** and `code` markers to HTML."""
    esc = _html.escape(text, quote=False)
    esc = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
    esc = _re.sub(r"`([^`\n]+)`", r"<code>\1</code>", esc)
    return esc


def send(chat_id, text, buttons=None):
    parts = _chunks(_to_html(text))
    last = None
    for i, part in enumerate(parts):
        kw = {"chat_id": chat_id, "text": part, "parse_mode": "HTML",
              "disable_web_page_preview": True}
        if buttons and i == len(parts) - 1:
            kw["reply_markup"] = {"inline_keyboard": buttons}
        try:
            last = _api("sendMessage", **kw)
        except Exception:
            kw["text"] = _re.sub(r"</?(b|code)>", "", part)
            kw.pop("parse_mode", None)
            try:
                last = _api("sendMessage", **kw)
            except Exception as e:
                print("send failed:", repr(e), flush=True)
    return last


def _edit(chat_id, msg_id, text, buttons="keep"):
    """editMessageText. buttons: list to replace, [] to clear, 'keep' to leave."""
    parts = _chunks(_to_html(text))
    if len(parts) > 1:
        # Telegram edits replace the whole message; a card longer than one chunk
        # is safer sent fresh than truncated in place.
        return send(chat_id, text, buttons if buttons != "keep" else None)
    kw = {"chat_id": chat_id, "message_id": msg_id, "text": parts[0],
          "parse_mode": "HTML", "disable_web_page_preview": True}
    if buttons == "keep":
        pass
    elif buttons == []:
        kw["reply_markup"] = {"inline_keyboard": []}
    else:
        kw["reply_markup"] = {"inline_keyboard": buttons}
    try:
        return _api("editMessageText", **kw)
    except Exception:
        kw["text"] = _re.sub(r"</?(b|code)>", "", parts[0])
        kw.pop("parse_mode", None)
        try:
            return _api("editMessageText", **kw)
        except Exception as e:
            print("edit failed:", repr(e), flush=True)
            return None


TIKTOK_RE = ("tiktok.com", "vm.tiktok", "vt.tiktok")


def _is_tiktok_link(text):
    return text and text.startswith("http") and any(d in text for d in TIKTOK_RE)


def _download_telegram_file(file_id):
    info = _api("getFile", file_id=file_id)
    fp = info["result"]["file_path"]
    dest = str(Path(config.WORK_DIR) / f"tg-{uuid.uuid4().hex[:12]}.mp4")
    Path(config.WORK_DIR).mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(f"{FILE_API}/{fp}", dest)
    return dest


def _is_free(user_id):
    return not db.is_pro(user_id)


def _check_quota(chat_id, user_id):
    left = db.quota_left(user_id)
    if left is None:
        return True  # pro
    if left <= 0:
        link = billing.create_checkout_link(user_id)
        msg = (f"You've used all {config.FREE_MONTHLY_LIMIT} free videos this month. "
               f"Upgrade to **{config.BRAND_NAME} Pro** for unlimited.")
        buttons = [[{"text": "⭐ Upgrade", "url": link}]] if link else None
        send(chat_id, msg, buttons)
        return False
    return True


def _duration_reject(dur):
    limit = config.FREE_MAX_VIDEO_SECONDS
    return (f"⏱️ That video runs **{dur} seconds** and the free plan covers videos "
            f"up to **{limit} seconds**. Send a shorter clip, or upgrade for unlimited.")


def _check_duration(chat_id, user_id, duration, msg_id):
    """F12 gate. Free users get a friendly rejection over the limit. Unknown
    duration (None) passes, so a probe failure never blocks a user."""
    if not _is_free(user_id):
        return True
    if duration and duration > config.FREE_MAX_VIDEO_SECONDS:
        _edit(chat_id, msg_id, _duration_reject(duration), [])
        return False
    return True


# --- rendering ---------------------------------------------------------------

def _status_icon(status):
    return _STATUS_ICON.get((status or "").lower(), "📄")


def _split_tags(tags):
    return [t for t in (tags or "").split(",") if t.strip()]


def _badges_line(item, status):
    bits = []
    if item.get("id"):
        bits.append(f"`#{item['id']}`")
    bits.append(item.get("stage", ""))
    bits.append(item.get("action_type", ""))
    bits.append(f"Impact {item.get('impact', 3)}/5 · Effort {item.get('effort', 3)}/5")
    bits.append(f"{_status_icon(status)} {status}")
    return " · ".join(bits)


def _card_body(item, status):
    tags = _split_tags(item.get("tags"))
    tags_line = "**Tags**: " + ", ".join(f"#{t}" for t in tags) if tags else ""
    return (
        f"**{item.get('summary', '')}**\n\n"
        f"{_badges_line(item, status)}\n\n"
        f"**Key Ideas**\n{item.get('key_ideas', '')}\n\n"
        f"**Why It Matters**\n{item.get('why_it_matters', '')}\n\n"
        f"**Recommendations**\n{item.get('recommendations', '')}\n\n"
        f"{tags_line}"
    )


def _pending_card(note, triage, footer=""):
    item = {
        "id": None,
        "summary": note.get("summary", ""),
        "key_ideas": note.get("key_ideas", ""),
        "why_it_matters": note.get("why_it_matters", ""),
        "recommendations": note.get("recommendations", ""),
        "tags": ",".join(note.get("tags", [])),
        "stage": triage.get("stage", "Inbox"),
        "action_type": triage.get("action_type", "Just reference"),
        "impact": triage.get("impact", 3),
        "effort": triage.get("effort", 3),
    }
    return _card_body(item, "inbox") + footer


def _saved_card(item):
    return _card_body(item, item.get("status", "inbox"))


def _pending_buttons():
    return [
        [{"text": "💾 Save", "callback_data": "save"},
         {"text": "✖️ Discard", "callback_data": "discard"}],
        [{"text": "▶️ Open video", "callback_data": "open"},
         {"text": "📄 Transcript", "callback_data": "transcript"}],
    ]


def _saved_buttons(vid):
    return [
        [{"text": "▶️ Open video", "callback_data": f"open:{vid}"},
         {"text": "📄 Transcript", "callback_data": f"transcript:{vid}"},
         {"text": "🏷 Tag", "callback_data": f"tag:{vid}"}],
        [{"text": "🔄 Status", "callback_data": f"status:{vid}"},
         {"text": "♻️ Regenerate", "callback_data": f"regen:{vid}"},
         {"text": "📤 Share", "callback_data": f"share:{vid}"},
         {"text": "🗑 Delete", "callback_data": f"delete:{vid}"}],
    ]


def _row_text(item):
    s = item.get("summary") or "(no summary)"
    if len(s) > 70:
        s = s[:67] + "..."
    return (f"`#{item['id']}` [{item.get('stage', '')}] "
            f"[{_status_icon(item.get('status'))} {item.get('status', '')}] "
            f"⚡{item.get('impact', 3)}/{item.get('effort', 3)} · {s}")


def _actions_row_text(item):
    s = item.get("summary") or "(no summary)"
    if len(s) > 80:
        s = s[:77] + "..."
    return (f"`#{item['id']}` [{item.get('action_type', '')}] "
            f"⚡{item.get('impact', 3)}/{item.get('effort', 3)} · {s}")


def _share_text(item):
    tags = _split_tags(item.get("tags"))
    tags_line = "**Tags**: " + ", ".join(f"#{t}" for t in tags) if tags else ""
    body = (
        f"**{item.get('summary', '')}**\n\n"
        f"**Key Ideas**\n{item.get('key_ideas', '')}\n\n"
        f"**Why It Matters**\n{item.get('why_it_matters', '')}\n\n"
        f"**Recommendations**\n{item.get('recommendations', '')}\n\n"
        f"{tags_line}"
    )
    url = item.get("source_url") or ""
    if url:
        body += f"\n\nSource: {url}"
    return body


# --- processing --------------------------------------------------------------

def _process_transcript(chat_id, user_id, transcript, source_url, msg_id):
    try:
        note = analyze.analyze_note(transcript)
    except Exception as e:
        _edit(chat_id, msg_id, "⚠️ I read it but couldn't analyze it just now. Try again in a moment.", [])
        print("analyze_note error:", repr(e), flush=True)
        return
    try:
        triage = analyze.analyze_triage({**note, "transcript": transcript})
    except Exception as e:
        print("triage error:", repr(e), flush=True)
        triage = {"stage": "Inbox", "action_type": "Just reference", "impact": 3, "effort": 3}
    if msg_id is None:
        # no processing message to resolve (direct call): send a fresh card
        last = send(chat_id, _pending_card(note, triage), _pending_buttons())
        if last and last.get("result"):
            msg_id = last["result"]["message_id"]
    _PENDING[(chat_id, msg_id)] = {"url": source_url, "note": note,
                                   "transcript": transcript, "triage": triage}
    db.record_usage(user_id, source_url)
    left = db.quota_left(user_id)
    footer = "" if left is None else f"\n\n({left} free videos left this month)"
    _edit(chat_id, msg_id, _pending_card(note, triage) + footer, _pending_buttons())


def _process_file(chat_id, user_id, file_path, source_url, msg_id):
    if _is_free(user_id):
        dur = ingest.probe_file_duration(file_path)
        if not _check_duration(chat_id, user_id, dur, msg_id):
            return
    try:
        transcript = analyze.transcribe_local(file_path)
        if not transcript.strip():
            raise ValueError("empty transcript")
        note = analyze.analyze_note(transcript)
    except Exception as e:
        _edit(chat_id, msg_id, "⚠️ I couldn't read that file just now. Try again in a moment.", [])
        print("process_file error:", repr(e), flush=True)
        return
    _process_transcript(chat_id, user_id, transcript, source_url, msg_id)


def process_job(job):
    """Run one queued job. Called by the background worker thread.

    Mirrors the old synchronous flow: duration gate for free users, ElevenLabs
    server-side transcription first, download + local whisper as the fallback,
    then the note + triage card. The ack message resolves into the card.
    Unhandled failures notify the user and re-raise so the worker marks the
    job failed.
    """
    chat_id = job["chat_id"]
    user_id = job["telegram_id"]
    msg_id = job["ack_message_id"]
    url = job["source_url"] or ""

    try:
        if job["kind"] == "file":
            path = _download_telegram_file(job["file_id"])
            _process_file(chat_id, user_id, path, url, msg_id)
            return

        if _is_free(user_id):
            dur = ingest.probe_duration(url)
            if not _check_duration(chat_id, user_id, dur, msg_id):
                return
        ok, transcript, _terr = ingest.transcript_from_url(url)
        if ok:
            _process_transcript(chat_id, user_id, transcript, url, msg_id)
            return
        print(f"[ingest] elevenlabs source_url failed for {url}: {_terr[:300]}", flush=True)

        result = ingest.ingest(url)
        if not result.ok:
            print(f"[ingest] all adapters failed for {url}: {result.error[-400:]}", flush=True)
            _edit(chat_id, msg_id,
                  "❌ I couldn't read that one. " + result.error.split("\n")[0] +
                  "\n\nTip: open it in TikTok, tap Share → Save Video, and send me the "
                  "file directly, that always works.", [])
            return
        if not _check_duration(chat_id, user_id, result.duration, msg_id):
            return
        _process_file(chat_id, user_id, result.file_path, url, msg_id)
    except Exception:
        _edit(chat_id, msg_id,
              "⚠️ Something went wrong on my end with that one. Please send it again.", [])
        raise


# The background worker. Started from main(); tests drive it with pump().
WORKER = worker.Worker(process_job)


# --- command handlers --------------------------------------------------------

def _parse_id(args, usage):
    if not args or not args[0].isdigit():
        send(usage)
        return None
    return int(args[0])


def _cmd_vault(chat_id, user_id, stage_arg=None):
    _render_vault(chat_id, user_id, None, 0, stage_arg)


def _render_vault(chat_id, user_id, msg_id, page, stage_key=None):
    stage = _STAGE_KEY.get(stage_key) if stage_key else None
    limit = 20
    total = db.count_vault(user_id, stage=stage)
    if total == 0:
        text = "Your vault is empty. Save an idea with the 💾 button."
        if msg_id:
            _edit(chat_id, msg_id, text, [])
        else:
            send(chat_id, text)
        return
    pages = max(1, (total + limit - 1) // limit)
    page = max(0, min(page, pages - 1))
    offset = page * limit
    items = db.list_vault(user_id, limit=limit, offset=offset, stage=stage)
    lines = [_row_text(i) for i in items]
    header = f"**Your vault** ({total} saved)"
    if stage:
        header += f" · filtered by **{stage}**"
    lines.append(f"\nPage {page + 1} of {pages}")
    buttons = [
        [{"text": "All", "callback_data": "vault:0:all"},
         {"text": "📥 Inbox", "callback_data": "vault:0:inbox"},
         {"text": "📚 Reference", "callback_data": "vault:0:ref"},
         {"text": "⚡ Worth Acting On", "callback_data": "vault:0:act"}],
    ]
    nav = []
    nav.append({"text": "⬅️ Prev", "callback_data": f"vault:{page - 1}:{stage_key or 'all'}",
                "disabled": page == 0})
    nav.append({"text": f"{page + 1}/{pages}", "callback_data": "noop"})
    nav.append({"text": "Next ➡️", "callback_data": f"vault:{page + 1}:{stage_key or 'all'}",
                "disabled": page + 1 >= pages})
    buttons.append(nav)
    text = header + "\n\n" + "\n".join(lines)
    if msg_id:
        _edit(chat_id, msg_id, text, buttons)
    else:
        send(chat_id, text, buttons)


def _cmd_search(chat_id, user_id, q):
    if not q:
        send(chat_id, "Usage: /search <word> with optional stage:act, tag:name, impact:4")
        return
    items = db.search_vault(user_id, q)
    if not items:
        send(chat_id, f"No saved ideas match “{q}”.")
        return
    lines = [_row_text(i) for i in items]
    footer = ("\n\nFilter with stage:act, tag:name, impact:4, type:content. "
              "Open one with /transcript <id>.")
    send(chat_id, f"**Matches for “{q}”:**\n\n" + "\n".join(lines) + footer)


def _render_actions(chat_id, user_id, msg_id):
    items = db.actions(user_id, limit=15)
    if not items:
        text = "All clear, nothing worth acting on right now. Send a TikTok and I'll triage it."
        if msg_id:
            _edit(chat_id, msg_id, text, [])
        else:
            send(chat_id, text)
        return
    total = db.actions_total(user_id)
    lines = [_actions_row_text(i) for i in items]
    header = ("**Actions queue** · worth doing next\n"
              "Sorted by impact over effort. Done clears it, Later sends it to "
              "reference, Snooze brings it back tomorrow.")
    if total > len(items):
        header += f"\n{total - len(items)} more in the queue, handle these first."
    buttons = []
    for i in items:
        vid = i["id"]
        buttons.append([
            {"text": "✅ Done", "callback_data": f"action_done:{vid}"},
            {"text": "🕐 Later", "callback_data": f"action_later:{vid}"},
            {"text": "💤 Snooze", "callback_data": f"action_snooze:{vid}"},
        ])
    text = header + "\n\n" + "\n".join(lines)
    if msg_id:
        _edit(chat_id, msg_id, text, buttons)
    else:
        send(chat_id, text, buttons)


def _cmd_plan(chat_id, user_id):
    user = db.get_user(user_id) or {}
    plan = user.get("plan", "free")
    if plan == "pro":
        lines = ["**Plan**: Pro", "Videos this month: unlimited", "Duration limit: none"]
    else:
        used = db.month_usage(user_id)
        left = db.quota_left(user_id)
        lines = [
            "**Plan**: Free",
            f"Videos this month: {used} of {config.FREE_MONTHLY_LIMIT}",
            f"Videos left: {left}",
            f"Duration limit: {config.FREE_MAX_VIDEO_SECONDS} seconds per video",
        ]
    lines.append("")
    lines.append("Upgrade for unlimited videos and no duration limit.")
    link = billing.create_checkout_link(user_id)
    buttons = [[{"text": "⭐ Upgrade to Pro", "url": link}]] if link else None
    send(chat_id, "\n".join(lines), buttons)


def _tag_editor_text(item):
    current = _split_tags(item.get("tags"))
    lines = [f"**Tags for #{item['id']}**"]
    if current:
        lines.append("Current: " + ", ".join(f"#{t}" for t in current))
    else:
        lines.append("Current: none")
    lines.append("Tap a chip to remove it, tap a suggestion to add it, or use "
                 "/tag <id> add <tag> and /tag <id> remove <tag>.")
    return "\n".join(lines)


def _tag_editor_buttons(user_id, item):
    vid = item["id"]
    current = set(_split_tags(item.get("tags")))
    rows = []
    for t in sorted(current):
        rows.append([{"text": f"✖️ {t}", "callback_data": f"tagdel:{vid}:{t[:30]}"}])
    suggestions = [t for t, _c in db.all_tags(user_id, 10) if t not in current][:6]
    for t in suggestions:
        rows.append([{"text": f"➕ {t}", "callback_data": f"tagadd:{vid}:{t[:30]}"}])
    rows.append([{"text": "✅ Done", "callback_data": f"tagdone:{vid}"}])
    return rows


def _cmd_tag(chat_id, user_id, parts):
    usage = "Usage: /tag <id> [add <tag>... | remove <tag>...]"
    vid = _parse_id(parts[1:], usage)
    if vid is None:
        return
    item = db.get_vault_item(user_id, vid)
    if not item:
        send(chat_id, f"No saved idea with id #{vid}.")
        return
    if len(parts) == 2:
        send(chat_id, _tag_editor_text(item), _tag_editor_buttons(user_id, item))
        return
    sub = parts[2].lower()
    if sub == "add" and len(parts) > 3:
        tags = parts[3:]
        db.add_tags(user_id, vid, tags)
        item = db.get_vault_item(user_id, vid)
        send(chat_id, f"Added to #{vid}: " + ", ".join(f"#{t}" for t in tags) +
             f"\n\nCurrent: " + ", ".join(f"#{t}" for t in _split_tags(item.get("tags"))))
    elif sub == "remove" and len(parts) > 3:
        tags = parts[3:]
        db.remove_tags(user_id, vid, tags)
        item = db.get_vault_item(user_id, vid)
        send(chat_id, f"Removed from #{vid}: " + ", ".join(f"#{t}" for t in tags) +
             f"\n\nCurrent: " + ", ".join(f"#{t}" for t in _split_tags(item.get("tags"))))
    else:
        send(chat_id, usage)


def _cmd_transcript(chat_id, user_id, vid):
    item = db.get_vault_item(user_id, vid)
    if not item:
        send(chat_id, f"No saved idea with id #{vid}.")
        return
    t = item.get("transcript") or "No transcript stored for this one."
    send(chat_id, f"**Transcript #{vid}**\n\n{t}",
         [[{"text": "📋 Copy as file", "callback_data": f"copyfile:{vid}"}]])


def _cmd_regen(chat_id, user_id, vid):
    item = db.get_vault_item(user_id, vid)
    if not item:
        send(chat_id, f"No saved idea with id #{vid}.")
        return
    send(chat_id, "♻️ Regenerating the note…")
    try:
        note = analyze.analyze_note(item.get("transcript") or "")
    except Exception as e:
        send(chat_id, "⚠️ Regenerate failed, try again in a moment.")
        print("regen error:", repr(e), flush=True)
        return
    db.update_note(user_id, vid, note)
    item = db.get_vault_item(user_id, vid)
    send(chat_id, _saved_card(item), _saved_buttons(vid))


def _cmd_share(chat_id, user_id, vid):
    item = db.get_vault_item(user_id, vid)
    if not item:
        send(chat_id, f"No saved idea with id #{vid}.")
        return
    send(chat_id, _share_text(item))


def _cmd_status(chat_id, user_id, parts):
    usage = "Usage: /status <id> [inbox | in progress | done | archived]"
    vid = _parse_id(parts[1:], usage)
    if vid is None:
        return
    item = db.get_vault_item(user_id, vid)
    if not item:
        send(chat_id, f"No saved idea with id #{vid}.")
        return
    if len(parts) > 2:
        wanted = " ".join(parts[2:]).lower()
        if wanted not in db.STATUS_CYCLE:
            send(chat_id, "Status must be one of: inbox, in progress, done, archived.")
            return
        db.set_status(user_id, vid, wanted)
        new = wanted
    else:
        new = db.next_status(item.get("status", "inbox"))
        db.set_status(user_id, vid, new)
    item = db.get_vault_item(user_id, vid)
    send(chat_id, _saved_card(item), _saved_buttons(vid))


def _cmd_delete(chat_id, user_id, vid):
    item = db.get_vault_item(user_id, vid)
    if not item:
        send(chat_id, f"No saved idea with id #{vid}.")
        return
    db.delete_note(user_id, vid)
    send(chat_id, f"🗑 Deleted #{vid}.")


# --- message dispatch --------------------------------------------------------

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    user_id = user.get("id")
    db.upsert_user(user_id, user.get("username") or user.get("first_name", ""))
    text = msg.get("text", "")

    if text.startswith("/start"):
        send(chat_id,
             f"👋 Welcome to **{config.BRAND_NAME}**.\n\n"
             "Send me a TikTok link (or the video file itself) and I'll transcribe it and "
             "turn it into an organized note: a summary, the key ideas, why it matters for "
             "your businesses, and what to do next. Save the good ones to your vault.\n\n"
             f"You get **{config.FREE_MONTHLY_LIMIT} free videos a month**. /vault to see saved, "
             "/actions for what's worth doing next, /plan for your quota, /upgrade for unlimited.")
        return

    if text.startswith("/upgrade"):
        link = billing.create_checkout_link(user_id)
        if link:
            send(chat_id, "Upgrade to unlimited:", [[{"text": "⭐ Upgrade to Pro", "url": link}]])
        else:
            send(chat_id, "Billing isn't configured yet, hang tight.")
        return

    if text.startswith("/vault"):
        parts = text.split()
        stage_arg = parts[1].lower() if len(parts) > 1 else None
        stage_map = {"all": "all", "inbox": "inbox", "in": "inbox",
                     "ref": "ref", "reference": "ref",
                     "act": "act", "acting": "act", "worth": "act"}
        _cmd_vault(chat_id, user_id, stage_map.get(stage_arg))
        return

    if text.startswith("/search"):
        q = text[len("/search"):].strip()
        _cmd_search(chat_id, user_id, q)
        return

    if text.startswith("/actions"):
        _render_actions(chat_id, user_id, None)
        return

    if text.startswith("/plan"):
        _cmd_plan(chat_id, user_id)
        return

    if text.startswith("/tag"):
        _cmd_tag(chat_id, user_id, text.split())
        return

    if text.startswith("/transcript"):
        vid = _parse_id(text.split()[1:], "Usage: /transcript <id>")
        if vid is not None:
            _cmd_transcript(chat_id, user_id, vid)
        return

    if text.startswith(("/regen", "/regenerate")):
        vid = _parse_id(text.split()[1:], "Usage: /regen <id>")
        if vid is not None:
            _cmd_regen(chat_id, user_id, vid)
        return

    if text.startswith("/share"):
        vid = _parse_id(text.split()[1:], "Usage: /share <id>")
        if vid is not None:
            _cmd_share(chat_id, user_id, vid)
        return

    if text.startswith("/status"):
        _cmd_status(chat_id, user_id, text.split())
        return

    if text.startswith("/delete"):
        vid = _parse_id(text.split()[1:], "Usage: /delete <id>")
        if vid is not None:
            _cmd_delete(chat_id, user_id, vid)
        return

    # A TikTok link: acknowledge instantly, queue the heavy work for the worker.
    if _is_tiktok_link(text):
        if not _check_quota(chat_id, user_id):
            return
        processing = send(chat_id, "🎬 Got it, working on it…")
        msg_id = processing["result"]["message_id"] if processing and processing.get("result") else None
        db.enqueue_job(chat_id, user_id, text, kind="link", ack_message_id=msg_id)
        return

    # A video file / video note attached
    vid = msg.get("video") or msg.get("document") or msg.get("video_note")
    if vid and vid.get("file_id"):
        if not _check_quota(chat_id, user_id):
            return
        processing = send(chat_id, "🎬 Got the file, working on it…")
        msg_id = processing["result"]["message_id"] if processing and processing.get("result") else None
        db.enqueue_job(chat_id, user_id, "uploaded-file", kind="file",
                       file_id=vid["file_id"], ack_message_id=msg_id)
        return

    send(chat_id, "Send me a TikTok link or the video file and I'll get to work. /start for help.")


# --- callback dispatch -------------------------------------------------------

def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    user_id = cb["from"]["id"]
    msg_id = cb["message"]["message_id"]
    data = cb.get("data", "")
    key = (chat_id, data)
    now = time.time()
    if data == "save" and now - _RECENT_CB.get(key, 0) < 90:
        _api("answerCallbackQuery", callback_query_id=cb["id"],
             text="Already on it, give me a few seconds 👍")
        return
    _RECENT_CB[key] = now
    _api("answerCallbackQuery", callback_query_id=cb["id"])

    parts = data.split(":")
    action = parts[0]
    args = parts[1:]

    if action == "noop":
        return

    if action == "save":
        pending = _PENDING.get((chat_id, msg_id))
        if not pending:
            _edit(chat_id, msg_id, "That one expired, send the TikTok again.", [])
            return
        vid = db.save_note(user_id, pending["url"], pending["note"],
                           pending["transcript"], pending["triage"])
        _PENDING.pop((chat_id, msg_id), None)
        item = db.get_vault_item(user_id, vid)
        _edit(chat_id, msg_id, _saved_card(item), _saved_buttons(vid))
        _api("answerCallbackQuery", callback_query_id=cb["id"], text=f"Saved as #{vid}")
        return

    if action == "discard":
        _PENDING.pop((chat_id, msg_id), None)
        _edit(chat_id, msg_id, "✖️ Discarded, nothing saved.", [])
        return

    if action == "open":
        url = ""
        if args:
            item = db.get_vault_item(user_id, int(args[0])) if args[0].isdigit() else None
            url = (item or {}).get("source_url") or ""
        else:
            pending = _PENDING.get((chat_id, msg_id))
            url = (pending or {}).get("url") or ""
        if url:
            send(chat_id, url)
        else:
            send(chat_id, "No source link on this one.")
        return

    if action == "transcript":
        if not args or not args[0].isdigit():
            return
        item = db.get_vault_item(user_id, int(args[0]))
        if not item:
            send(chat_id, f"No saved idea with id #{args[0]}.")
            return
        vid = item["id"]
        t = item.get("transcript") or "No transcript stored for this one."
        send(chat_id, f"**Transcript #{vid}**\n\n{t}",
             [[{"text": "📋 Copy as file", "callback_data": f"copyfile:{vid}"}]])
        return

    if action == "copyfile":
        if not args or not args[0].isdigit():
            return
        item = db.get_vault_item(user_id, int(args[0]))
        if not item:
            return
        send_document(chat_id, f"snag-{item['id']}-transcript.txt",
                      item.get("transcript") or "", caption=f"Transcript for #{item['id']}")
        return

    if action in ("tag", "tagadd", "tagdel", "tagdone"):
        if not args or not args[0].isdigit():
            return
        vid = int(args[0])
        item = db.get_vault_item(user_id, vid)
        if not item:
            send(chat_id, f"No saved idea with id #{vid}.")
            return
        if action == "tag":
            _edit(chat_id, msg_id, _tag_editor_text(item), _tag_editor_buttons(user_id, item))
            return
        if action == "tagadd":
            db.add_tags(user_id, vid, [args[1]])
            item = db.get_vault_item(user_id, vid)
            _edit(chat_id, msg_id, _tag_editor_text(item), _tag_editor_buttons(user_id, item))
            _api("answerCallbackQuery", callback_query_id=cb["id"], text=f"Added #{args[1]}")
            return
        if action == "tagdel":
            db.remove_tags(user_id, vid, [args[1]])
            item = db.get_vault_item(user_id, vid)
            _edit(chat_id, msg_id, _tag_editor_text(item), _tag_editor_buttons(user_id, item))
            _api("answerCallbackQuery", callback_query_id=cb["id"], text=f"Removed #{args[1]}")
            return
        # tagdone: resolve the editor back into the item card
        _edit(chat_id, msg_id, _saved_card(item), _saved_buttons(vid))
        return

    if action == "status":
        if not args or not args[0].isdigit():
            return
        vid = int(args[0])
        item = db.get_vault_item(user_id, vid)
        if not item:
            send(chat_id, f"No saved idea with id #{vid}.")
            return
        new = db.next_status(item.get("status", "inbox"))
        db.set_status(user_id, vid, new)
        item = db.get_vault_item(user_id, vid)
        _edit(chat_id, msg_id, _saved_card(item), _saved_buttons(vid))
        _api("answerCallbackQuery", callback_query_id=cb["id"], text=f"Status: {new}")
        return

    if action == "regen":
        if not args or not args[0].isdigit():
            return
        vid = int(args[0])
        item = db.get_vault_item(user_id, vid)
        if not item:
            send(chat_id, f"No saved idea with id #{vid}.")
            return
        _edit(chat_id, msg_id, "♻️ Regenerating the note…")
        try:
            note = analyze.analyze_note(item.get("transcript") or "")
        except Exception as e:
            _edit(chat_id, msg_id, "⚠️ Regenerate failed, try again in a moment.", [])
            print("regen error:", repr(e), flush=True)
            return
        db.update_note(user_id, vid, note)
        item = db.get_vault_item(user_id, vid)
        _edit(chat_id, msg_id, _saved_card(item), _saved_buttons(vid))
        _api("answerCallbackQuery", callback_query_id=cb["id"], text="Note regenerated")
        return

    if action == "share":
        if not args or not args[0].isdigit():
            return
        item = db.get_vault_item(user_id, int(args[0]))
        if item:
            send(chat_id, _share_text(item))
        return

    if action == "delete":
        if not args or not args[0].isdigit():
            return
        vid = int(args[0])
        db.delete_note(user_id, vid)
        _edit(chat_id, msg_id, f"🗑 Deleted #{vid}.", [])
        _api("answerCallbackQuery", callback_query_id=cb["id"], text="Deleted")
        return

    if action in ("action_done", "action_later", "action_snooze"):
        if not args or not args[0].isdigit():
            return
        vid = int(args[0])
        if action == "action_done":
            db.set_status(user_id, vid, "done")
            feedback = "Done, nice work."
        elif action == "action_later":
            db.set_stage(user_id, vid, "Reference")
            feedback = "Moved to Reference."
        else:
            db.snooze(user_id, vid, int(time.time()) + 86400)
            feedback = "Snoozed until tomorrow."
        _render_actions(chat_id, user_id, msg_id)
        _api("answerCallbackQuery", callback_query_id=cb["id"], text=feedback)
        return

    if action == "vault":
        page = int(args[0]) if args and args[0].isdigit() else 0
        stage_key = args[1] if len(args) > 1 else "all"
        _render_vault(chat_id, user_id, msg_id, page, stage_key)
        return


def main():
    db.init()
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set, add it to .env (from @BotFather).")
    WORKER.start()
    print(f"[{config.BRAND_NAME}] polling…")
    offset = None
    while True:
        try:
            resp = _api("getUpdates", timeout=60, offset=offset)
            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    if "message" in upd:
                        msg = upd["message"]
                        print(f"[msg] {msg.get('from',{}).get('id')}: "
                              f"{(msg.get('text') or '<media>')[:80]}", flush=True)
                        handle_message(msg)
                    elif "callback_query" in upd:
                        handle_callback(upd["callback_query"])
                except Exception as e:
                    print("update error:", repr(e), flush=True)
                    chat = (upd.get("message") or {}).get("chat", {}).get("id")
                    if chat:
                        try:
                            send(chat, "⚠️ Something went wrong on my end with that one. "
                                       "Please send it again.")
                        except Exception:
                            pass
        except Exception as e:
            print("loop error:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
