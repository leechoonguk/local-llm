# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Constants
# ============================================================

# What a reader may send in one turn. Long enough for a paragraph about a
# product, short enough that the request body is bounded.
MESSAGE_MAX_LENGTH = 2000

# The events a turn is made of, named on the wire so a client switches on the
# name rather than on the shape of `data`: the answer arrives as many `token`
# events and exactly one `end`, and a turn that fails ends with `error`
# instead - a stream that just stops is indistinguishable from a lost network.
ChatEvent = Literal["token", "end", "error"]

# The code an `error` event carries when the answerer is down - the same word
# the 503 handler puts in a body (`app/core/exceptions.py`), so a client maps
# one failure to one sentence whether it arrived as a status or as an event.
SERVICE_UNAVAILABLE_CODE = "service_unavailable"


# ============================================================
# Classes
# ============================================================


class FoodChatAskRequest(BaseModel):
    """One turn a reader sends: what they typed, nothing else.

    No conversation id and no history: this surface holds no state - the
    answer is a function of this message alone (`app/services/food/chat.py`),
    and a client that wants context sends it in the message.
    """

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=MESSAGE_MAX_LENGTH)


class FoodChatTokenEvent(BaseModel):
    """One piece of the answer, in the order it was written.

    An `*Event`, not a `*ReadResponse`: it is what the stream says at a
    moment, not a row read - it has no id to be keyed by and no revision to
    lock against, and calling it a read would owe both.
    """

    model_config = ConfigDict(extra="forbid")

    text: str


class FoodChatEndEvent(BaseModel):
    """The turn is over: the whole answer, and how many pieces it arrived in.

    The full text is repeated here on purpose - a client that joined the
    stream late, or dropped a token, has one authoritative answer to keep
    rather than whatever its buffer holds.
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    tokens: int


class FoodChatErrorEvent(BaseModel):
    """The turn ended badly, said inside the stream.

    A code, not a sentence: the client already maps codes to words
    (`serverErrorMessage`), and a message written here would be a second
    place the same failure is worded.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
