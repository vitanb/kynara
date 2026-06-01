#!/usr/bin/env python3
"""
Generate ElevenLabs voice narration clips for demo.html.

Usage:
    python scripts/generate_demo_audio.py

Requires:
    pip install requests

Output:
    frontend/public/audio/narration_0.mp3 ... narration_7.mp3

Then open demo.html — it will use the real audio files automatically.
"""
import os
import sys
import json
import time
import pathlib
import requests

# ── Config ──────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("ELEVENLABS_API_KEY", "sk_ff6740534f57f936939498f1e20a228d22197bdd9fd9235f")
BASE_URL = "https://api.elevenlabs.io/v1"

# Rachel — warm, clear, professional American female voice
# Swap VOICE_ID for any voice from: GET /v1/voices
VOICE_ID = "fVVjLtJgnQI61CoImgHU"  # American male voice

MODEL_ID = "eleven_turbo_v2_5"   # fastest + best quality; use eleven_multilingual_v2 for accents

OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "frontend" / "public" / "audio"

VOICE_SETTINGS = {
    "stability": 0.45,
    "similarity_boost": 0.82,
    "style": 0.30,
    "use_speaker_boost": True,
}

# ── Narration scripts ────────────────────────────────────────────────────────
SCRIPTS = [
    # 0 — Hero / intro
    (
        "narration_0",
        "Welcome to Kynara — the permission control plane for AI agents. "
        "As AI agents start taking real actions in the world — reading customer data, "
        "issuing refunds, restarting servers — you need a way to control exactly what "
        "they're allowed to do, and prove it. That's what Kynara solves."
    ),
    # 1 — Decision request
    (
        "narration_1",
        "Every time an AI agent wants to call a tool, it sends a decision request to Kynara. "
        "The request includes the agent's identity, the action it wants to take, "
        "the resource it wants to act on, and ambient context — like the current time "
        "and the caller's location."
    ),
    # 2 — RBAC gate
    (
        "narration_2",
        "Kynara first runs a role-based access control check. "
        "Does this agent have a role that grants the requested scope? "
        "Importantly, agents can never have more authority than the human user they're "
        "acting on behalf of. This non-escalation guarantee is hardwired into the engine — "
        "it cannot be bypassed by policy."
    ),
    # 3 — ABAC conditions
    (
        "narration_3",
        "Then the attribute-based engine evaluates policy conditions. "
        "Is it within business hours? Is the request coming from an allowed country? "
        "Does the transaction amount exceed the approval threshold? "
        "Conditions are evaluated as a safe JSON syntax tree — "
        "no code execution, no injection surface."
    ),
    # 4 — Playground
    (
        "narration_4",
        "Let's see it live. You can run a real policy decision right here in the playground. "
        "Change the action, resource, country, or time of day — and watch the decision "
        "flow animate with the result. Try the after-hours scenario to see "
        "the require-approval outcome in action."
    ),
    # 5 — Approvals
    (
        "narration_5",
        "When a policy returns require-approval, the agent doesn't guess or retry — "
        "it pauses completely. The approval request appears in the human review queue "
        "with full context: which agent, which action, what the risk score is, "
        "and how long until it expires. Only after a human approves can the agent continue."
    ),
    # 6 — Audit chain
    (
        "narration_6",
        "Every single decision — allow, deny, or approval — is appended to a "
        "SHA-256 hash-chained audit log. The chain links each event to the one before it. "
        "If anyone modifies or deletes a past record, the chain breaks. "
        "You can verify the entire log's integrity with a single API call — "
        "with no dependency on Kynara being online."
    ),
    # 7 — CTA
    (
        "narration_7",
        "Kynara is free to get started: three seats, ten thousand policy decisions per month, "
        "the full policy engine, approvals, JIT grants, and the tamper-evident audit log. "
        "You can wire it into a Python or TypeScript agent in under five minutes. "
        "Sign up at kynara AI dot com — no credit card required."
    ),
]


def list_voices():
    """Print all available voices so you can pick a different one."""
    r = requests.get(f"{BASE_URL}/voices", headers={"xi-api-key": API_KEY})
    r.raise_for_status()
    for v in r.json()["voices"]:
        labels = v.get("labels", {})
        print(f"  {v['voice_id']:30s}  {v['name']:20s}  {labels.get('gender',''):8s}  {labels.get('accent',''):12s}  {labels.get('use_case','')}")


def generate_clip(name: str, text: str, out_path: pathlib.Path) -> None:
    print(f"  Generating {name} ({len(text)} chars)...")
    url = f"{BASE_URL}/text-to-speech/{VOICE_ID}"
    payload = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": VOICE_SETTINGS,
        "output_format": "mp3_44100_128",
    }
    r = requests.post(url, headers={"xi-api-key": API_KEY, "Content-Type": "application/json"}, json=payload)
    if r.status_code != 200:
        print(f"    ✗ Error {r.status_code}: {r.text[:200]}")
        return
    out_path.write_bytes(r.content)
    kb = len(r.content) // 1024
    print(f"    ✓ Saved {out_path.name} ({kb} KB)")


def main():
    if "--list-voices" in sys.argv:
        print("Available voices:")
        list_voices()
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Voice ID: {VOICE_ID}  Model: {MODEL_ID}\n")

    for i, (name, text) in enumerate(SCRIPTS):
        out = OUTPUT_DIR / f"{name}.mp3"
        if out.exists() and "--force" not in sys.argv:
            print(f"  Skipping {name}.mp3 (already exists — use --force to regenerate)")
            continue
        generate_clip(name, text, out)
        if i < len(SCRIPTS) - 1:
            time.sleep(0.4)  # gentle rate limiting

    print(f"\n✓ Done. {len(SCRIPTS)} clips in {OUTPUT_DIR}")
    print("  Open demo.html — it will use these files automatically.")
    print("\n  To use a different voice, run:")
    print("    python scripts/generate_demo_audio.py --list-voices")
    print("  Then set VOICE_ID at the top of this script and re-run with --force.")


if __name__ == "__main__":
    main()
