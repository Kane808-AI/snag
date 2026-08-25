"""
CLI proof harness — run the full pipeline on a URL without Telegram.

    python3 test_pipeline.py "https://www.tiktok.com/t/XXXX"    # download -> transcribe -> note -> triage
    python3 test_pipeline.py --file /path/to/video.mp4           # local file transcription

Proves transcript -> note -> triage end to end, mirroring bot.py's real flow.
Transcription is free: YouTube native captions or local faster-whisper.
Requires DEEPSEEK_API_KEY for the note/triage steps.
"""
import sys
import config
import ingest
import analyze


def _show_note(note):
    tags = ", ".join(note.get("tags", []))
    print("\n" + "=" * 60)
    print("SUMMARY:", note.get("summary", ""))
    print("\nKEY IDEAS:\n" + note.get("key_ideas", ""))
    print("\nWHY IT MATTERS:\n" + note.get("why_it_matters", ""))
    print("\nRECOMMENDATIONS:\n" + note.get("recommendations", ""))
    print("\nTAGS:", tags)
    print("=" * 60)


def main(argv):
    file_path = None
    transcript = None

    if "--file" in argv:
        i = argv.index("--file")
        file_path = argv[i + 1]
        print(f"[transcribe] using local file: {file_path}")
    else:
        url = argv[1]
        print(f"[transcribe] {url}")
        if ingest.is_youtube(url):
            ok, transcript, err = ingest.youtube_transcript(url)
            if ok:
                print(f"[transcribe] ok via YouTube captions, {len(transcript)} chars")
            else:
                print(f"[transcribe] captions failed ({err}); falling back to download")
        if transcript is None:
            result = ingest.ingest(url)
            if not result.ok:
                print("INGEST FAILED:\n" + result.error)
                return 1
            print(f"[ingest] ok via {result.source}  dur={result.duration}s  file={result.file_path}")
            file_path = result.file_path

    if file_path:
        transcript = analyze.transcribe_local(file_path)
        if not transcript or not transcript.strip():
            print("LOCAL TRANSCRIPT EMPTY")
            return 1
        print(f"[transcribe] local whisper, {len(transcript)} chars")

    if not config.DEEPSEEK_API_KEY:
        print("\n[analyze] SKIPPED — no DEEPSEEK_API_KEY set. Transcription proven; "
              "set the key to run analysis.")
        return 0

    print(f"[analyze] model={config.DEEPSEEK_MODEL} …")
    note = analyze.analyze_note(transcript)
    _show_note(note)

    print("[triage] scoring…")
    triage = analyze.analyze_triage({**note, "transcript": transcript})
    print(f"STAGE: {triage['stage']} · ACTION: {triage['action_type']} · "
          f"IMPACT: {triage['impact']}/5 · EFFORT: {triage['effort']}/5")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
