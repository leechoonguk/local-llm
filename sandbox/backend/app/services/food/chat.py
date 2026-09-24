# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.food.chat import FoodChatEndEvent, FoodChatTokenEvent


# ============================================================
# Constants
# ============================================================

# The pause between two pieces of an answer. It is what makes the stream
# observable: without it every token lands in the same tick and the screen
# shows the finished answer at once, which is a POST wearing a stream's
# clothes. 40ms reads as typing rather than as a stutter.
TOKEN_DELAY_SECONDS = 0.04

# The answer this surface gives, in the pieces it gives it in. A stand-in with
# no model behind it: the point of the endpoint is the transport - a client
# that renders tokens as they land, an error that arrives as an event, a
# disconnect the generator sees - and swapping this function for a real
# answerer changes nothing else.
GREETING = "안녕하세요. 식품 데이터에 대해 무엇이든 물어보세요."


# ============================================================
# Classes
# ============================================================


class FoodChatService:
    """One turn of chat, streamed. No table, no history: the answer is a function of the message."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def answer(self, message: str) -> AsyncIterator[FoodChatTokenEvent]:
        """The answer to one message, a piece at a time, in the order it is written.

        An async generator rather than a list, because the router hands each
        piece to the client as it arrives; a list would arrive whole and the
        stream would be a formality. The caller's disconnect reaches the
        generator as a cancellation at the `sleep`, which is where a real
        answerer would stop asking its model.
        """
        for piece in _pieces(message):
            await asyncio.sleep(TOKEN_DELAY_SECONDS)
            yield FoodChatTokenEvent(text=piece)

    @staticmethod
    def summarise(pieces: list[str]) -> FoodChatEndEvent:
        """The turn's last event: the whole answer, and how many pieces it arrived in."""
        return FoodChatEndEvent(text="".join(pieces), tokens=len(pieces))


# ============================================================
# Functions
# ============================================================


def _pieces(message: str) -> list[str]:
    """The stand-in answer, split the way it is streamed - one piece per word, spaces kept.

    Split on spaces rather than on characters so a Korean sentence arrives in
    units a reader can read as they land; the space is carried with the word
    before it, so joining the pieces returns the answer exactly.
    """
    answer = f"'{message.strip()}' 라고 하셨네요. {GREETING}"
    words = answer.split(" ")
    return [word if index == len(words) - 1 else f"{word} " for index, word in enumerate(words)]
