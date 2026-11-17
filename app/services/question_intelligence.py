"""Smart prompt auto-repair, Hinglish/shorthand normalization, and interactive
doubt/clarification detection for natural conversational PDF Q&A.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

# Common shorthand and typo corrections for imperfect user prompts
_TYPO_MAP: dict[str, str] = {
    "wht": "what",
    "wat": "what",
    "whch": "which",
    "hw": "how",
    "abt": "about",
    "plz": "please",
    "pls": "please",
    "limt": "limit",
    "limts": "limits",
    "limitation": "limitations",
    "requirment": "requirement",
    "requirments": "requirements",
    "reqs": "requirements",
    "req": "requirement",
    "sumary": "summary",
    "summery": "summary",
    "summerize": "summarize",
    "objecive": "objective",
    "objectve": "objective",
    "documnt": "document",
    "doc": "document",
    "purpos": "purpose",
    "peroid": "period",
    "deadlin": "deadline",
    "architecure": "architecture",
    "constrain": "constraint",
    "constrains": "constraints",
    "boundry": "boundary",
    "boundries": "boundaries",
    "explan": "explain",
    "explian": "explain",
    "specfication": "specification",
    "spec": "specification",
    "refnd": "refund",
    "subscrption": "subscription",
    "elligible": "eligible",
    "eligble": "eligible",
    "authntication": "authentication",
    "verfication": "verification",
    "citaton": "citation",
    "citatons": "citations",
    "pge": "page",
    "pg": "page",
    "pgs": "pages",
    "numbr": "number",
    "maxmum": "maximum",
    "minmum": "minimum",
}

# Conversational Hinglish phrases mapped to clear English document queries
_HINGLISH_PHRASE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:iska|iski|is\s+pdf\s+ka|document\s+ka)\s+(?:main\s+)?(?:summary|saraansh|overview|matlab|topic|uddeshya|purpose)\s+(?:kya\s+hai|batao|de\s+do|likho)\b",
            re.IGNORECASE,
        ),
        "What is the main purpose, overview, and summary of this document?",
    ),
    (
        re.compile(
            r"\b(?:yeh|ye)\s+(?:pdf|document|file)\s+kis\s+(?:baare|bare)\s+(?:mein|me|mai)\s+hai\b",
            re.IGNORECASE,
        ),
        "What is this document about and what is its main objective?",
    ),
    (
        re.compile(
            r"\b(?:iska|iski|pdf\s+ki|document\s+ki)?\s*limit(?:s|ations?)?\s+(?:kya\s+hai|kya\s+h|kitni\s+hai|batao)\b",
            re.IGNORECASE,
        ),
        "What are the limits and limitations stated in this document?",
    ),
    (
        re.compile(
            r"\b(?:kaun\s*se|kaunsa|kis)\s+page\s+(?:par|pe|mein|me|mai)\s+(?:hai|diya\s+hai|likha\s+hai)\b",
            re.IGNORECASE,
        ),
        "Which PDF page mentions that?",
    ),
    (
        re.compile(
            r"\b(?:kya\s+kya|kya)\s+requirements?\s+(?:hai|hain|h|batao)\b",
            re.IGNORECASE,
        ),
        "What are the key requirements stated in this document?",
    ),
)

_HINGLISH_STOP_REPLACEMENTS: dict[str, str] = {
    "kya": "what",
    "hai": "is",
    "hain": "are",
    "batao": "explain",
    "bataye": "explain",
    "samjhao": "explain",
    "kaunsa": "which",
    "kaunse": "which",
    "kitna": "how much",
    "kitne": "how many",
    "kab": "when",
    "kyu": "why",
    "kaise": "how",
    "iska": "its",
    "iski": "its",
    "iske": "its",
    "mein": "in",
    "mai": "in",
}

# Prompts that are bare/vague and have no clear topic on their own
_BARE_DOUBT_PATTERN = re.compile(
    r"^\s*(?:"
    r"help|doubt|i\s+have\s+a\s+doubt|mujhe\s+doubt\s+hai|confused|"
    r"tell\s+me|explain|explain\s+please|details|more\s+details|info|information|"
    r"what\s+is\s+it|what\s+does\s+it\s+mean|what\s+about\s+it|what\s+about\s+that|"
    r"explain\s+that|explain\s+this\s+part|which\s+one|what\s+is\s+that|"
    r"which\s+page\s+is\s+it\s+on|just\s+give\s+that\s+page|"
    r"tell\s+me\s+more|elaborate|can\s+you\s+explain|kya\s+hai|batao|samjhao|\?+"
    r")\s*[?.!]*\s*$",
    re.IGNORECASE,
)

# Deictic/pronoun-only questions that require prior history to make sense
_UNANCHORED_PRONOUN_PATTERN = re.compile(
    r"^\s*(?:what|which|how|when|where|why|who|can\s+you|please|just)?\s*"
    r"(?:is|are|was|were|does|do|did|about|explain|describe|show|give|tell\s+me\s+about)?\s*"
    r"(?:it|that|those|them|the\s+other\s+one|the\s+previous\s+one|the\s+former|the\s+latter|that\s+page|those\s+pages)"
    r"\s*(?:mean|say|work|apply|mentioned|on|for|in\s+detail)?\s*[?.!]*\s*$",
    re.IGNORECASE,
)

_HEADING_CANDIDATE_RE = re.compile(
    r"^(?:(?:\d+(?:\.\d+)*)\s+[A-Z][^\n]{3,65}|[A-Z][A-Za-z0-9 ,/&–—-]{4,55})$"
)


@dataclass(frozen=True)
class DoubtCheckResult:
    """Outcome of checking whether a user question requires clarification first."""

    needs_clarification: bool
    clarification_message: str | None = None
    clarification_options: tuple[str, ...] = ()


def smart_repair_question(raw_question: str) -> tuple[str, bool]:
    """Automatically clean, repair typos, and normalize informal/Hinglish prompts.

    Returns ``(effective_question, was_repaired)``.
    Never alters exact technical codes, model names, or numbers.
    """
    cleaned = " ".join((raw_question or "").strip().split())
    if not cleaned:
        return "", False

    # 1. Check full-phrase Hinglish patterns first
    for pattern, replacement in _HINGLISH_PHRASE_PATTERNS:
        if pattern.search(cleaned):
            return replacement, True

    # 2. Token-level typo and Hinglish normalization
    words = cleaned.split(" ")
    repaired_words: list[str] = []
    changed = False

    # Count how many Hinglish markers appear
    lower_tokens = [re.sub(r"[^\w]", "", w.lower()) for w in words]
    has_hinglish = sum(1 for t in lower_tokens if t in _HINGLISH_STOP_REPLACEMENTS) >= 2

    for word in words:
        prefix_match = re.match(r"^([^\w]*)(.*?)([^\w]*)$", word)
        if not prefix_match:
            repaired_words.append(word)
            continue
        lead, core, trail = prefix_match.groups()
        # Preserve words with digits, hyphens, or uppercase acronyms (e.g., NIST, 800-63B, PlanA1)
        if not core or any(ch.isdigit() for ch in core) or (core.isupper() and len(core) > 1):
            repaired_words.append(word)
            continue

        lower_core = core.lower()
        if lower_core in _TYPO_MAP:
            replacement = _TYPO_MAP[lower_core]
            if core[0].isupper():
                replacement = replacement.capitalize()
            repaired_words.append(f"{lead}{replacement}{trail}")
            changed = True
        elif has_hinglish and lower_core in _HINGLISH_STOP_REPLACEMENTS:
            replacement = _HINGLISH_STOP_REPLACEMENTS[lower_core]
            repaired_words.append(f"{lead}{replacement}{trail}")
            changed = True
        else:
            repaired_words.append(word)

    result = " ".join(repaired_words).strip()

    # 3. If the user typed a bare fragment like "purpose and scope" or "upload limits",
    # keep it natural; if Hinglish reordered words awkwardly, polish it.
    if has_hinglish and changed:
        # Extract key English topic words to form a clean question
        topic_words = [
            re.sub(r"[^\w-]", "", w)
            for w in result.split()
            if re.sub(r"[^\w-]", "", w).lower()
            not in {"what", "is", "are", "explain", "in", "the", "of", "its", "this", "pdf", "document"}
            and len(re.sub(r"[^\w-]", "", w)) > 1
        ]
        if topic_words:
            topic_str = " ".join(topic_words)
            result = f"What does the document state about {topic_str}?"

    return result, (result.casefold() != cleaned.casefold())


def extract_document_topic_suggestions(
    pages: Sequence[object],
    *,
    file_name: str = "the PDF",
    max_options: int = 4,
) -> tuple[str, ...]:
    """Build 3-4 document-specific clickable clarification questions from PDF pages."""
    headings: list[str] = []
    for page in pages[:12]:
        text = getattr(page, "text", "") or ""
        for raw_line in text.splitlines():
            line = " ".join(raw_line.strip().split())
            if not line or len(line) < 4 or len(line) > 65:
                continue
            if _HEADING_CANDIDATE_RE.match(line):
                cleaned_heading = re.sub(r"^\d+(?:\.\d+)*\s*", "", line).strip(" .:-")
                if (
                    len(cleaned_heading) >= 4
                    and cleaned_heading.lower() not in {h.lower() for h in headings}
                ):
                    headings.append(cleaned_heading)
                if len(headings) >= 3:
                    break
        if len(headings) >= 3:
            break

    suggestions: list[str] = []
    for heading in headings[:2]:
        suggestions.append(f"What does the document state about {heading}?")

    defaults = (
        "What is the main purpose and scope of this document?",
        "What limits, thresholds, or deadlines are stated?",
        "What key requirements or conditions apply?",
    )
    for d in defaults:
        if len(suggestions) >= max_options:
            break
        if d.lower() not in {s.lower() for s in suggestions}:
            suggestions.append(d)

    return tuple(suggestions[:max_options])


def check_question_doubt(
    *,
    question: str,
    history: Sequence[tuple[str, str]] = (),
    pages: Sequence[object] = (),
    file_name: str = "this PDF",
) -> DoubtCheckResult:
    """Check whether the user's question is ambiguous/unanchored and needs clarification first.

    If prior conversation history exists, pronouns can be resolved from history,
    so we only ask for clarification when history is empty (or when the user
    explicitly asks a bare 1-word/doubt prompt).
    """
    cleaned = (question or "").strip()
    if not cleaned:
        return DoubtCheckResult(needs_clarification=False)

    # If the user asks a bare doubt prompt ("help", "doubt", "confused", "explain", "?")
    is_bare_doubt = _BARE_DOUBT_PATTERN.match(cleaned) is not None
    is_unanchored_pronoun = (
        not history and _UNANCHORED_PRONOUN_PATTERN.match(cleaned) is not None
    )

    if not is_bare_doubt and not is_unanchored_pronoun:
        return DoubtCheckResult(needs_clarification=False)

    # If history exists and it's a follow-up cue like "just give that page" or "explain that",
    # let history resolution handle it rather than blocking!
    if history and not re.match(
        r"^\s*(?:help|doubt|i\s+have\s+a\s+doubt|mujhe\s+doubt\s+hai|confused|\?+)\s*[?.!]*\s*$",
        cleaned,
        re.IGNORECASE,
    ):
        return DoubtCheckResult(needs_clarification=False)

    options = extract_document_topic_suggestions(pages, file_name=file_name)
    message = (
        f"I want to make sure I give you an accurate, source-verified answer from "
        f"**{file_name}**, and your question looks a bit broad or refers to something "
        f"not yet mentioned in our chat. Could you clarify which topic you'd like me to check, "
        f"or pick one of the suggestions below?"
    )
    return DoubtCheckResult(
        needs_clarification=True,
        clarification_message=message,
        clarification_options=options,
    )


def resolve_clarification_followup(
    question: str,
    history: Sequence[tuple[str, str]],
) -> str | None:
    """If the user is replying to a clarification question, combine context deterministically."""
    if len(history) < 2:
        return None
    last_role, last_content = history[-1]
    if last_role != "assistant":
        return None
    if (
        "Could you clarify" not in last_content
        and "Which one would you like" not in last_content
    ):
        return None

    # Find the user's question right before the clarification
    prior_user_q = ""
    for role, content in reversed(history[:-1]):
        if role == "user" and content.strip():
            prior_user_q = content.strip()
            break

    reply = question.strip()
    # If the reply is already a full question (e.g. clicked a chip), use it directly!
    if len(reply.split()) >= 5 or reply.endswith("?"):
        return reply

    if prior_user_q and not _BARE_DOUBT_PATTERN.match(prior_user_q):
        return f"{prior_user_q.rstrip('?.!')} regarding {reply}?"
    return f"What does the document state about {reply}?"
