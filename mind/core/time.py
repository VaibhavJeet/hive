"""
Single source of "now" (HIVE-036).

`datetime.utcnow()` is deprecated from Python 3.12 and appeared **360 times across 70
files**. The obvious fix — swap each one for `datetime.now(timezone.utc)` — would be
wrong here, and expensively so: all 65 `DateTime` columns in the schema are naive, so
half-migrated code would compare aware values against naive ones and raise
`TypeError: can't compare offset-naive and offset-aware datetimes` at runtime, in
whichever code path happened to mix them.

So this is done in two steps:

1. **Now** — every call site uses `utcnow()` below, which returns exactly what
   `datetime.utcnow()` returned (naive UTC) via the non-deprecated API. Behaviour is
   identical; the deprecation is gone; and "what time is it" becomes one decision in one
   place instead of 360.
2. **Later** — making the system timezone-aware is then a change to *this function* plus
   a migration moving the columns to `DateTime(timezone=True)`. That step needs a live
   database to verify and is tracked as its own task.

Use `utcnow()` for anything that will be stored or compared against stored values.
`aware_utcnow()` is available for new code that never touches the legacy columns.
"""

from datetime import datetime, timezone

__all__ = ["utcnow", "aware_utcnow"]


def utcnow() -> datetime:
    """Current UTC time as a **naive** datetime.

    Identical in value to the deprecated `datetime.utcnow()`. Naive on purpose: it must
    stay comparable with the 65 naive `DateTime` columns until they are migrated.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def aware_utcnow() -> datetime:
    """Current UTC time as a timezone-aware datetime.

    Safe only where the value will not be compared against, or stored in, the legacy
    naive columns.
    """
    return datetime.now(timezone.utc)
