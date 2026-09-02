# ============================================================
# Imports
# ============================================================

from pydantic import BaseModel, ConfigDict


# ============================================================
# Classes
# ============================================================


class Page[T](BaseModel):
    """One page of a collection, and how large the collection is.

    Every list endpoint answers in this shape. A bare array cannot say how much
    it is a page of, and the client that has to know reaches for the only signal
    an array carries: ask for one row more than fits and infer "there is
    another page" from getting it. That inference is not a count — it can say
    *more*, never *how many* — so a reader paging a log saw `1–10` until the
    last page told them the number they wanted on the first.

    `total` is the count under the same filter as `items`, without the window:
    the answer to "how many are there", not "how many did I just receive".
    """

    model_config = ConfigDict(extra="forbid")

    items: list[T]
    total: int
