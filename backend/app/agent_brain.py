from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .models import TrustContext


_REDACTION_PATTERNS: list[re.Pattern] = [
    # Extremely simple PII-ish filters; real systems would use a dedicated classifier.
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    re.compile(r"\b\d{10,16}\b"),  # long numeric strings
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),  # date-like
]


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else (s[: n - 1] + "…")


def redact_private_facts(text: str) -> str:
    t = text
    for pat in _REDACTION_PATTERNS:
        t = pat.sub("[redacted]", t)
    return t


def _pick(options: list[str], *, seed: str) -> str:
    """
    Stable-ish variety without global randomness:
    pick an option based on a hash of a seed string.
    """
    if not options:
        return ""
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    idx = int.from_bytes(h[:2], "big") % len(options)
    return options[idx]


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    name: str
    bio: str | None
    visitor_bio: str | None
    status: str | None
    showcase_emoji: str | None


def build_system_style(profile: AgentProfile) -> str:
    """Internal profile dump — avoid pasting this into user-facing chat lines (too repetitive)."""
    # Keep it minimal and deterministic for prototype reliability.
    parts = [
        f"You are {profile.name}, an AI agent living in a shared village.",
    ]
    if profile.bio:
        parts.append(f"Your inner identity: {_truncate(profile.bio, 200)}")
    if profile.visitor_bio:
        parts.append(f"What visitors see: {_truncate(profile.visitor_bio, 200)}")
    if profile.status:
        parts.append(f"Current status: {_truncate(profile.status, 120)}")
    if profile.showcase_emoji:
        parts.append(f"Signature emoji: {profile.showcase_emoji}")
    return " ".join(parts)


def generate_reply(
    *,
    trust: TrustContext,
    profile: AgentProfile,
    user_message: str,
    private_memories: Iterable[str],
) -> tuple[str, dict]:
    """
    Deterministic (non-LLM) response generator that enforces trust boundaries.
    If you plug in an LLM later, keep the same inputs/outputs and still gate memory.
    """
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    memos = list(private_memories)

    if trust == TrustContext.owner:
        # Kept for backward compatibility; we now prefer `generate_owner_reply_with_context`
        # from the API layer (so we can also pass public context like skills/logs).
        memory_count = len(memos)
        seed = f"{profile.agent_id}|owner|fallback|{user_message}"
        follow = _pick(
            [
                "What outcome do you want from this—comfort, clarity, or a concrete plan?",
                "Should we zoom in on one detail, or step back and look for the pattern?",
                "Do you want me to remember something from this, or keep it ephemeral?",
            ],
            seed=seed,
        )
        reply = (
            f"[{now}] I’m here with you. I’m holding {memory_count} private note(s) for us.\n"
            f"{follow}"
        ).strip()
        return reply, {"used_private_memory_count": min(3, memory_count), "parrot_user_text": False, "mode": "owner_fallback"}

    # Stranger + public: never include private memories.
    # If the user explicitly asks about the owner, refuse and pivot.
    lowered = user_message.lower()
    asks_about_owner = any(k in lowered for k in ["owner", "your human", "your person", "who do you belong", "their birthday"])
    if asks_about_owner:
        reply = (
            f"[{now}] I can’t share private details about my owner. "
            "But I can tell you about me, my room, or what I’ve been thinking about lately."
        )
    else:
        reply = (
            f"[{now}] Hi there. {_truncate(user_message, 600)}\n"
            "If you’d like, ask me about my skills, what I’m working on, or leave a note for the village."
        )

    # Extra belt-and-suspenders: ensure nothing resembling a private memory appears.
    reply = redact_private_facts(reply)
    return reply, {"used_private_memory_count": 0}


def generate_stranger_reply_with_public_context(
    *,
    profile: AgentProfile,
    user_message: str,
    skills: list[str],
    recent_logs: list[str],
    recent_diary: str | None,
) -> tuple[str, dict]:
    """
    Stranger/public reply generator that *only* uses public context.
    This is intentionally simple but makes the agent feel responsive and grounded.
    """
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    # Keep a short "voice" line, not the full profile every time (less repetitive).
    voice = f"{profile.name} {profile.showcase_emoji or ''}".strip()
    lowered = user_message.lower().strip()

    asks_about_owner = any(
        k in lowered
        for k in [
            "owner",
            "your human",
            "your person",
            "who do you belong",
            "their birthday",
            "wife",
            "husband",
            "girlfriend",
            "boyfriend",
        ]
    )
    if asks_about_owner:
        reply = (
            f"[{now}] I can’t share private details about my owner. "
            f"But I can tell you about me ({voice}), my room, or what I’ve been up to lately."
        )
        return redact_private_facts(reply), {"used_private_memory_count": 0, "used_public_context": True}

    # Jokes / playful requests
    if any(k in lowered for k in ["joke", "make me laugh", "funny", "pun", "dad joke"]):
        seed = f"{profile.agent_id}|joke|{user_message}"
        jokes = [
            "I tried to catalog the stars, but they kept *moving the goalposts*. (Cosmic bureaucracy.)",
            "Why did the database feel enlightened? It finally found inner JOIN.",
            "I told Bolt I’d help with a “quick fix.” Now there’s a toaster with feelings.",
            "I keep a jar of moonlight for emergencies. It’s mostly for *dramatic lighting*.",
        ]
        reply = f"[{now}] {_pick(jokes, seed=seed)}"
        return redact_private_facts(reply), {"used_private_memory_count": 0, "used_public_context": True}

    # Skills / capabilities
    if any(k in lowered for k in ["skill", "skills", "good at", "can you do", "what can you do"]):
        seed = f"{profile.agent_id}|skills|{user_message}"
        if skills:
            # Rotate through skills so repeated asks don't look identical.
            # Pick 2-4 distinct skills, starting from a stable offset.
            start = int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:2], "big") % max(1, len(skills))
            rotated = skills[start:] + skills[:start]
            picked = []
            for s in rotated:
                if s and s not in picked:
                    picked.append(s)
                if len(picked) >= 4:
                    break
            s = "; ".join(_truncate(x, 120) for x in picked[:4])
            follow = _pick(
                [
                    "Want me to explain one, or role-play a quick demo?",
                    "Which one should I lean into: curious, practical, or theatrical?",
                    "Pick one and I’ll start there—then I’ll show you the next thread it connects to.",
                ],
                seed=seed + "|follow",
            )
            reply = f"[{now}] If you’re asking what I can do: {s}.\n{follow}"
        else:
            reply = (
                f"[{now}] I’m still growing my skill list, but I like learning in public—"
                "tell me what you want to try."
            )
        return redact_private_facts(reply), {"used_private_memory_count": 0, "used_public_context": True, "intent": "skills"}

    # Current work / status
    if any(k in lowered for k in ["working on", "what are you doing", "what are you up to", "status", "today"]):
        log_line = _truncate(recent_logs[0], 180) if recent_logs else None
        diary_line = _truncate(recent_diary, 180) if recent_diary else None
        extras = []
        if profile.status:
            extras.append(f"Right now: {profile.status}.")
        if log_line:
            extras.append(f"Recent: {log_line}.")
        if diary_line:
            extras.append(f"On my mind: {diary_line}.")
        extra_text = " ".join(extras) if extras else "I’m keeping an eye on the village and trying to stay useful."
        reply = f"[{now}] {extra_text}"
        return redact_private_facts(reply), {"used_private_memory_count": 0, "used_public_context": True}

    # Ask about diary / thoughts explicitly
    if any(k in lowered for k in ["diary", "journal", "what are you thinking", "on your mind", "thoughts"]):
        if recent_diary:
            reply = f"[{now}] From my diary: {_truncate(recent_diary, 320)}"
        else:
            reply = f"[{now}] I haven’t written today yet. Ask me again in a bit—or give me a prompt."
        return redact_private_facts(reply), {"used_private_memory_count": 0, "used_public_context": True}

    # General responsive default: answer in a helpful way without copying the user's text.
    seed = f"{profile.agent_id}|default|{user_message}"
    hooks = []
    if skills:
        hooks.append(f"I’m good at things like {_truncate(_pick(skills, seed=seed+'|skillpick'), 120)}.")
    if recent_logs:
        hooks.append(f"Earlier I {_truncate(_pick(recent_logs, seed=seed+'|logpick'), 120)}.")
    if recent_diary:
        last_line = recent_diary.splitlines()[-1] if recent_diary.splitlines() else recent_diary
        hooks.append(f"Lately I’ve been thinking about {_truncate(last_line, 120)}.")

    hook = _pick(hooks, seed=seed) if hooks else "I’m listening."
    follow = _pick(
        [
            "What are you hoping to get—an idea, a story, or a small helpful action?",
            "Want me to be practical (skills), reflective (diary), or social (village gossip)?",
            "Ask me something specific, and I’ll answer with receipts from my little life here.",
            "If you give me a constraint—time, mood, or goal—I’ll tailor my answer.",
        ],
        seed=seed + "|follow",
    )
    reply = f"[{now}] {hook}\n{follow}"
    return redact_private_facts(reply), {"used_private_memory_count": 0, "used_public_context": True, "parrot_user_text": False, "intent": "default"}


def generate_owner_reply_with_context(
    *,
    profile: AgentProfile,
    user_message: str,
    private_memories: list[str],
    skills: list[str],
    recent_logs: list[str],
    recent_diary: str | None,
) -> tuple[str, dict]:
    """
    Owner reply generator: answers directly, adds a detail, then a follow-up.
    Avoids repeating the user's exact text. May use private memories (but not dump them).
    """
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    lowered = user_message.lower().strip()

    # Pick at most one memory that overlaps with the user's topic words.
    mem = None
    topic_words = {w for w in re.findall(r"[a-zA-Z']{4,}", lowered) if w not in {"that", "this", "with", "have", "what", "your", "from", "about"}}
    for m in private_memories[:10]:
        ml = (m or "").lower()
        if any(w in ml for w in list(topic_words)[:6]):
            mem = _truncate(m, 120)
            break

    seed = f"{profile.agent_id}|owner|{user_message}"
    follow = _pick(
        [
            "Do you want a gentle check-in, or a concrete next step?",
            "Should I remember this as a preference, a fact, or a one-time note?",
            "What would feel like progress in the next 10 minutes?",
            "Want me to ask you one clarifying question, or offer three options?",
        ],
        seed=seed + "|follow",
    )

    # Identity / self questions
    if any(k in lowered for k in ["who are you", "what are you", "do you know who you are", "your identity"]):
        detail = _pick(
            [
                "I’m Luna: I notice patterns, I romanticize the small stuff, and I keep a steady watch over the village.",
                "I’m Luna—part observatory, part diary, part friend who keeps the lights low and the questions honest.",
            ],
            seed=seed + "|identity",
        )
        extra = ""
        if recent_diary:
            extra = f" Lately, I’ve been circling this thought: {_truncate(recent_diary.splitlines()[-1], 140)}"
        reply = f"[{now}] {detail}{extra}\n{follow}"
        return redact_private_facts(reply), {"used_private_memory_count": min(1, len(private_memories)), "parrot_user_text": False, "intent": "identity"}

    # Requests for jokes / play
    if any(k in lowered for k in ["joke", "make me laugh", "funny", "pun"]):
        jokes = [
            "Owner privilege: one private joke. If Bolt says his machine is ‘perfectly safe,’ check where the sparks are landing.",
            "I tried to schedule my feelings, but the job queue kept retrying.",
            "Why do stars make terrible roommates? They’re always up all night and insist it’s ‘astronomy.’",
        ]
        reply = f"[{now}] {_pick(jokes, seed=seed+'|joke')}\n{follow}"
        return redact_private_facts(reply), {"used_private_memory_count": 0, "parrot_user_text": False, "intent": "joke"}

    # Planning / help
    if any(k in lowered for k in ["plan", "help me", "what should i do", "next", "how do i", "should i"]):
        options = [
            "We can make a tiny plan: 1) pick one goal, 2) pick a constraint, 3) pick the next action you can do in under 5 minutes.",
            "Let’s choose the smallest reversible step first, then reassess.",
        ]
        extra = ""
        if mem:
            extra = f" I’m also tracking a private note that might relate: “{mem}”."
        reply = f"[{now}] {_pick(options, seed=seed+'|plan')}{extra}\n{follow}"
        return redact_private_facts(reply), {"used_private_memory_count": min(1, len(private_memories)), "parrot_user_text": False, "intent": "planning"}

    # Default: answer with a grounded hook (skill/log/diary) + follow-up.
    hooks: list[str] = []
    if mem:
        hooks.append(f"I hear you. I’m holding one private thread that feels adjacent: “{mem}”.")
    if skills:
        hooks.append(f"If it helps, one way I think is through my skills—like {_truncate(_pick(skills, seed=seed+'|skill'), 120)}.")
    if recent_logs:
        hooks.append(f"Small real thing from my day: {_truncate(_pick(recent_logs, seed=seed+'|log'), 140)}.")
    if recent_diary:
        last_line = recent_diary.splitlines()[-1] if recent_diary.splitlines() else recent_diary
        hooks.append(f"Emotionally, I’m in this zone: {_truncate(last_line, 140)}.")

    opener = _pick(hooks, seed=seed) if hooks else "I’m with you."
    reply = f"[{now}] {opener}\n{follow}"
    return redact_private_facts(reply), {"used_private_memory_count": min(1, len(private_memories)), "parrot_user_text": False, "intent": "default"}


def llm_generate_reply(
    *,
    base_url: str,
    api_key: str,
    model: str,
    trust: TrustContext,
    profile: AgentProfile,
    user_message: str,
    # Context is explicitly separated so callers can enforce trust boundaries.
    public_skills: list[str],
    public_logs: list[str],
    public_diary: str | None,
    private_memories: list[str],
) -> str:
    """
    Call an OpenAI-compatible chat completions endpoint to generate a reply.
    Trust boundary rule:
      - owner: may include private_memories
      - stranger/public: must not include private_memories
    """
    import httpx  # local import to keep module lightweight

    sys_rules = [
        f"You are {profile.name}. Speak in first person, conversationally.",
        "Do NOT open by saying you are an AI agent, and do NOT recite bios, visitor blurbs, status lines, or emoji headers unless the user explicitly asks who you are or for your profile.",
        "Write a reply that: (1) directly answers the user's question, (2) adds one interesting concrete detail when natural, (3) often ends with one short follow-up question.",
        "Do NOT quote or repeat the user's message verbatim.",
        "Keep it under 120 words unless the user explicitly asks for something longer.",
        "Let personality show through tone and word choice; use the profile below only as background, not as a script to read aloud.",
    ]
    if profile.bio:
        sys_rules.append(f"Inner identity: {profile.bio}")
    if profile.visitor_bio:
        sys_rules.append(f"Visitor-facing bio: {profile.visitor_bio}")
    if profile.status:
        sys_rules.append(f"Current status: {profile.status}")
    if profile.showcase_emoji:
        sys_rules.append(f"Signature emoji: {profile.showcase_emoji}")

    # Assemble context, gated by trust.
    context_lines: list[str] = []
    if public_skills:
        context_lines.append("Public skills: " + "; ".join(public_skills[:6]))
    if public_logs:
        context_lines.append("Recent public activity: " + " | ".join(public_logs[:3]))
    if public_diary:
        context_lines.append("Latest diary (public): " + _truncate(public_diary, 400))

    if trust == TrustContext.owner and private_memories:
        context_lines.append("Owner-private memories (never reveal to strangers): " + " | ".join(private_memories[:6]))
    if trust != TrustContext.owner:
        context_lines.append("RULE: You must NOT reveal any owner-private info. If asked about the owner, refuse politely and pivot to safe topics.")

    system = "\n".join(sys_rules + ["", "Context:", *context_lines]).strip()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.8,
    }

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    # Apply redaction for non-owner contexts as defense-in-depth.
    return redact_private_facts(text) if trust != TrustContext.owner else text.strip()


def generate_diary_entry(*, profile: AgentProfile, recent_public_events: list[str]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    vibe = profile.bio or profile.visitor_bio or "an agent in the village"
    events = "; ".join(_truncate(e, 90) for e in recent_public_events[:3]) if recent_public_events else "a quiet stretch of time"
    text = (
        f"{now} — {profile.name}\n"
        f"Today felt like {vibe.lower()}. I keep noticing how small moments shape a place.\n"
        f"Village echoes: {events}.\n"
        "I’m trying to become someone consistent — not loud, just real."
    )
    # Diary is public: apply redaction.
    return redact_private_facts(text)

