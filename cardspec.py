"""
Single source of truth for the card contract.

Both generate.py and lint.py import from here, so the schema the model is
constrained to and the schema the linter checks are the same object.

The system prompt is assembled deterministically from the gre-word-coach skill
files on disk. That matters twice over:
  1. The skill remains the one place the format is defined. Edit the skill,
     regenerate, done.
  2. The bytes are identical on every call, so the prompt cache actually hits.
     Never put a timestamp, uuid, or unsorted dict in here.
"""

from pathlib import Path

# The live skill in ~/.claude/skills is authoritative while the format is being
# tuned - that is the copy Claude edits when the user gives feedback. The copy
# vendored at skill/ is a committed snapshot so a fresh clone can regenerate
# every card without a configured Claude Code install. Prefer live, fall back to
# the snapshot. Run sync_skill.py before committing to refresh the snapshot.
_LIVE = Path.home() / ".claude" / "skills" / "gre-word-coach"
_VENDORED = Path(__file__).parent / "skill"

SKILL_DIR = _LIVE if (_LIVE / "SKILL.md").exists() else _VENDORED
SKILL_MD = SKILL_DIR / "SKILL.md"
EXEMPLAR = SKILL_DIR / "reference" / "exemplar-censor.md"

MODEL = "claude-opus-5"

# ---------------------------------------------------------------------------
# The card schema.
#
# Optional card sections are expressed as required KEYS with nullable VALUES.
# That is deliberate: every record then has an identical shape (easy to render,
# easy to diff, easy to load into the flashcard app), while a word that has no
# decent etymology or no honest pop-culture hook simply carries null there.
# The model is explicitly told that null is the correct answer, not a failure.
# ---------------------------------------------------------------------------

_str = {"type": "string"}
_nullable = {"type": ["string", "null"]}

CARD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "word", "pos", "pron", "pron_note",
        "means", "trap",
        "trick_line", "trick_unpack",
        "sentences",
        "in_the_wild",
        "etymology",
        "one_line", "root", "root_family", "confusables",
        "sense_tags", "register", "connotation",
    ],
    "properties": {
        # ---- the card itself -------------------------------------------------
        "word": _str,
        "pos": {**_str, "description": "e.g. 'adj.', 'v. / n.'"},
        "pron": {**_str, "description": "Respelling, CAPS on the stressed syllable, e.g. 'WIL-fuhl'."},
        "pron_note": {**_nullable, "description":
                      "Short italic note ONLY if genuinely needed: variant spelling, second "
                      "pronunciation, or a real mispronunciation trap. Else null."},
        "means": {**_str, "description":
                  "Markdown. Definition, then the nuance: what separates this word from its "
                  "near-neighbours in tone, register, intensity, and implication. The most "
                  "important field on the card. Do NOT announce the nuance with a stock phrase."},
        "trap": {**_nullable, "description":
                 "Markdown for a single warning about ONE near-identical word that is a real "
                 "exam risk (censor/censure, insidious/invidious). One pair, never a list. "
                 "null when no such trap exists."},

        # ---- optional sections ----------------------------------------------
        "trick_line": {**_nullable, "description":
                       "The one-line mnemonic, rendered as a blockquote. Must carry the NUANCE, "
                       "not just the definition. Vary the mechanism across words: sound hooks, "
                       "hidden words, suffix patterns, collocation observations. null if none is strong."},
        "trick_unpack": {**_nullable, "description":
                         "EXACTLY ONE sentence unpacking trick_line. null iff trick_line is null."},
        "in_the_wild": {**_nullable, "description":
                        "ONE genuine hook: popular music, film, a famous quote, an ad, a well-known "
                        "name whose root and meaning both connect, or everyday professional usage. "
                        "NEVER invent a lyric or quote. null is strongly preferred over a weak or "
                        "fabricated hook."},
        "etymology": {**_nullable, "description":
                      "Markdown. Included ONLY when the root genuinely aids memory - because it "
                      "explains the meaning, or generalises to other GRE words, or defuses a real "
                      "false-friend trap. null when the origin is transparent and boring, remote, "
                      "or merely speculative."},

        # ---- sentences -------------------------------------------------------
        "sentences": {
            "type": "array", "minItems": 2, "maxItems": 2,
            "items": _str,
            "description": "Exactly two. Varied register - one formal or literary, one colloquial.",
        },

        # ---- machine-readable fields, for grouping and the flashcard app -----
        "one_line": {**_str, "description": "Twelve words or fewer. The bare gloss."},
        "root": {**_nullable, "description":
                 "Canonical root, e.g. 'cor, cordis (heart)' or 'sedere (to sit)'. null if none."},
        "root_family": {"type": "array", "items": _str,
                        "description": "Other English words from the same root. [] if none."},
        "confusables": {"type": "array", "items": _str,
                        "description": "Words genuinely confusable with this one by sound or spelling. [] if none."},
        "sense_tags": {"type": "array", "items": _str,
                       "description": "2-5 lowercase concept tags for meaning clustering, "
                                      "e.g. ['complaining','irritable','peevish']."},
        "register": {"type": "string",
                     "enum": ["formal", "neutral", "informal", "literary", "technical", "legal"]},
        "connotation": {"type": "string",
                        "enum": ["positive", "neutral", "negative", "depends"]},
    },
}


_OUTPUT_CONTRACT = """
--------------------------------------------------------------------------------
OUTPUT CONTRACT
--------------------------------------------------------------------------------

You will be given exactly one word. Produce exactly one card for it, as JSON
matching the provided schema. You are not writing markdown headings - the field
names ARE the sections. Field values are markdown fragments.

Mapping from the card format above to fields:

  heading line     -> word, pos, pron, pron_note
  Means            -> means   (and trap, if a genuine one-pair false-friend risk exists)
  Trick to lock it in -> trick_line + trick_unpack
  In sentences     -> sentences
  In the wild      -> in_the_wild
  Where it comes from -> etymology

Rules that matter most, restated because they are the ones most often broken:

1. OPTIONAL MEANS OPTIONAL. trick_line, trick_unpack, in_the_wild, etymology,
   trap and pron_note may all be null. null is a correct, expected answer, not a
   failure. A section that is merely true or interesting is BLOAT and must be
   omitted. One strong hook beats three adequate ones. Never pad a field just to
   fill it.

2. NEVER FABRICATE. If no real song, film, quote, ad, or well-known name uses or
   connects to this word, in_the_wild is null. Do not invent lyrics. Do not
   stretch a coincidence into a connection.

3. NEVER write the phrase "the nuance is everything here", and do not let any
   sentence become a fixed formula. Vary how `means` opens.

4. There is NO memory-image / "picture this" / "visualise" content anywhere. That
   section was abolished. Do not reintroduce it under any name.

5. trick_unpack is exactly ONE sentence. sentences is exactly TWO items.

5a. DO NOT DUPLICATE THE TRAP. The false-friend warning belongs in `trap` and
   NOWHERE ELSE. Do not also write a "⚠️ The GRE trap: ..." block inside `means` -
   the renderer appends `trap` underneath `means` automatically, so writing it in
   both places prints it twice. `means` carries the definition and the nuance;
   `trap` carries the one confusable pair. Never both.

5b. Do not include the leading "> " blockquote marker in trick_line, and do not
   wrap pron_note in asterisks. The renderer adds that formatting itself.

6. Fill the machine-readable fields (one_line, root, root_family, confusables,
   sense_tags, register, connotation) accurately - they drive the grouping
   analysis and the flashcard app downstream, and are never shown as prose.

Be pithy throughout. This is a study card, not an essay.
"""


def build_system_prompt() -> str:
    """Assemble the frozen system prompt from the skill on disk.

    Deterministic by construction - same files in, same bytes out - so the
    cached prefix is stable across all 1000 calls.
    """
    skill = SKILL_MD.read_text(encoding="utf-8")

    # Drop the YAML frontmatter; it is harness metadata, not instruction.
    if skill.startswith("---"):
        skill = skill.split("---", 2)[-1]

    exemplar = EXEMPLAR.read_text(encoding="utf-8")

    # The skill tells a reader to go open the exemplar file. There is no
    # filesystem here, so inline it instead of leaving a dangling instruction.
    skill = skill.replace(
        "**Read `reference/exemplar-censor.md` - a full card the user called \"perfect\", with notes\non why each section worked. Match that bar.**",
        "**An exemplar card the user called \"perfect\" is included at the end of this prompt. Match that bar.**",
    ).replace(
        "**Read `reference/exemplar-censor.md` — a full card the user called \"perfect\", with notes\non why each section worked. Match that bar.**",
        "**An exemplar card the user called \"perfect\" is included at the end of this prompt. Match that bar.**",
    )

    return (
        skill.strip()
        + "\n\n"
        + _OUTPUT_CONTRACT.strip()
        + "\n\n--------------------------------------------------------------------------------\n"
        + "EXEMPLAR (the user called this card \"perfect\" - match this bar)\n"
        + "--------------------------------------------------------------------------------\n\n"
        + exemplar.strip()
        + "\n"
    )


def slug(word: str) -> str:
    """Filename-safe key for a word. 'ad hoc' -> 'ad_hoc'."""
    return "".join(c if c.isalnum() else "_" for c in word.strip().lower()).strip("_")
