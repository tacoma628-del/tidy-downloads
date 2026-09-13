#!/usr/bin/env python3
"""Claude drafts a risk register, ChatGPT critiques it, Claude merges the two.

Demo script for a YouTube video aimed at production PMs — see
docs/designs/claude-chatgpt-pm-risk-register-video.md for the design doc.

Usage:
    export ANTHROPIC_API_KEY=...
    export OPENAI_API_KEY=...
    python3 video-demos/risk_register_demo.py
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # dotenv is optional — real env vars still work without it

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")

# Fictional project brief — safe to publish, no confidentiality concerns.
PROJECT_BRIEF = """
Project: "Riverbend" — a 12-week office fit-out for a 200-person tenant moving
into three floors of a downtown high-rise. Scope includes demolition of the
existing floor plan, new electrical and HVAC runs, furniture install, and a
phased move-in so the tenant's teams relocate one floor at a time. Fixed move-in
date driven by the tenant's own lease expiration on their old space. General
contractor is new to this building; landlord requires all work to happen
after business hours (6pm-6am) in the two occupied floors below.
""".strip()

DRAFT_PROMPT = f"""You are a construction project manager. Draft a risk register
for the following project. List 5-8 risks. For each: a short title, likelihood
(low/med/high), impact (low/med/high), and one-line mitigation. Output as a
numbered list, nothing else.

PROJECT BRIEF:
{PROJECT_BRIEF}
"""

CRITIQUE_PROMPT_TEMPLATE = """You are an outside risk reviewer brought in to
red-team another PM's risk register. Do not just rephrase their items — find
what's MISSING. Read the project brief and the draft register below, then list
only the risks the draft missed (if any), with the same format: title,
likelihood, impact, mitigation. If you genuinely find nothing missing, say so
plainly instead of inventing a weak risk.

PROJECT BRIEF:
{brief}

DRAFT REGISTER:
{draft}
"""

MERGE_PROMPT_TEMPLATE = """You drafted the risk register below. An outside
reviewer then critiqued it and found additional risks. Merge the reviewer's
findings into your original register to produce one final, clean numbered
list. Keep your original items, add the reviewer's genuinely new ones, and
note next to each added item "(added after review)".

YOUR DRAFT:
{draft}

REVIEWER'S CRITIQUE:
{critique}
"""


def fail(message: str) -> None:
    print(f"\nERROR: {message}\n", file=sys.stderr)
    sys.exit(1)


def get_anthropic_client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        fail("ANTHROPIC_API_KEY is not set. Get one at https://console.anthropic.com/settings/keys")
    try:
        import anthropic
    except ImportError:
        fail("The 'anthropic' package isn't installed. Run: pip install anthropic")
    return anthropic.Anthropic()


def get_openai_client():
    if not os.environ.get("OPENAI_API_KEY"):
        fail("OPENAI_API_KEY is not set. Get one at https://platform.openai.com/api-keys")
    try:
        import openai
    except ImportError:
        fail("The 'openai' package isn't installed. Run: pip install openai")
    return openai.OpenAI()


def claude_complete(client, model: str, prompt: str) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def openai_complete(client, model: str, prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def draft_risks(client) -> str:
    return claude_complete(client, ANTHROPIC_MODEL, DRAFT_PROMPT)


def critique_risks(client, draft: str) -> str:
    prompt = CRITIQUE_PROMPT_TEMPLATE.format(brief=PROJECT_BRIEF, draft=draft)
    return openai_complete(client, OPENAI_MODEL, prompt)


def merge_risks(client, draft: str, critique: str) -> str:
    prompt = MERGE_PROMPT_TEMPLATE.format(draft=draft, critique=critique)
    return claude_complete(client, ANTHROPIC_MODEL, prompt)


def main() -> None:
    anthropic_client = get_anthropic_client()
    openai_client = get_openai_client()

    print("=" * 70)
    print("STAGE 1 — Claude drafts the risk register")
    print("=" * 70)
    draft = draft_risks(anthropic_client)
    print(draft)

    print("\n" + "=" * 70)
    print("STAGE 2 — ChatGPT critiques the draft (looking only for gaps)")
    print("=" * 70)
    critique = critique_risks(openai_client, draft)
    print(critique)

    print("\n" + "=" * 70)
    print("STAGE 3 — Claude merges the critique into a final register")
    print("=" * 70)
    final = merge_risks(anthropic_client, draft, critique)
    print(final)


if __name__ == "__main__":
    main()
