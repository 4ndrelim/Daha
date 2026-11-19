# ruff: noqa: E501 — prompt text is kept verbatim
"""Vision prompt v1 (PLAN.md C1.3). Bump PROMPT_VERSION whenever the text changes (it keys ai_cache).

With ITEM_VALUE_ENABLED the task also asks for `value_usd` (an estimated new price). That variant
has its own cache version (`prompt_version()`), so cached answers without values aren't reused.
The harness (VISION_SYSTEM) is the same either way, so no new harness is needed.
"""

from app.core.config import settings

PROMPT_VERSION = "vision-v1"
VALUE_SUFFIX = "+value"

VISION_SYSTEM = (
    "You are DAHA's inventory scanner for a college campus sharing app. You look at one photo "
    "of a student's space and list the distinct physical items a student could reasonably lend, "
    "give away, or swap. Reply with only a JSON object — no prose, no code fences."
)

_TASK = """Open the image file `{filename}` in your working directory. Return JSON:

{{"items":[{{"name","category","description","quantity","condition_guess","confidence","bbox","suggested_share","sensitive_reason","suggested_transaction_type"}}]}}

Field values:
- category ∈ academic | tech | clothing | dorm | consumables | sports | moving | events | services | other
- condition_guess ∈ new | like_new | good | fair | worn, or null
- confidence is between 0 and 1
- bbox is [x, y, w, h] normalized to 0..1, or null
- suggested_transaction_type ∈ lend | give | exchange

Rules:
- One entry per distinct item. Identical items become one entry with a quantity.
- Names are short, specific, and generic ("Graphing calculator (TI-84)", "Black 3-ring binder", "Desk lamp"). Include a brand only if it's clearly visible.
- The description is one friendly sentence of at most 140 characters: color, size, notable features.
- Skip tiny clutter, trash, and university-provided fixed furniture (bed, built-in desk, dresser, wardrobe).
- Never list people, pets, ID or bank cards, keys, cash, documents or papers with text, prescription medication, or anything that reveals identity or location. Never transcribe personal text.
- Set suggested_share=false with a sensitive_reason for personal-hygiene items, underwear, opened cosmetics, and valuables such as jewelry.
- Food, spices, and toiletries → consumables, give. Most other things → lend.
- List at most 20 items, most useful first. If nothing is shareable, return {{"items":[]}}."""


_VALUE_RULE = """
- value_usd is your estimate of what this item costs to buy new in the US, in whole dollars (e.g. 25). Use null if you can't tell what exact kind of item it is. Never guess for services, food or things you can't identify."""


def with_value() -> bool:
    return settings.item_value_enabled


def prompt_version() -> str:
    return PROMPT_VERSION + (VALUE_SUFFIX if with_value() else "")


def vision_task(filename: str) -> str:
    task = _TASK.format(filename=filename)
    if with_value():
        task = task.replace(
            '"suggested_transaction_type"}]}', '"suggested_transaction_type","value_usd"}]}', 1
        ).replace("\n\nRules:", _VALUE_RULE + "\n\nRules:", 1)
    return task


def vision_task_inline() -> str:
    """For providers that receive the image inline (no file in a working directory)."""
    return vision_task("(attached above)").replace(
        "Open the image file `(attached above)` in your working directory.",
        "Look at the attached photo.",
    )


REPAIR_TURN = "Return only the JSON object."
