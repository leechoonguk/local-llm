"""FoodChatService tests — one turn, streamed in pieces that rejoin into the answer."""

import pytest

from app.services.food.chat import FoodChatService


@pytest.mark.asyncio
async def test_answer_streams_the_message_back_in_pieces_that_rejoin(factory) -> None:
    """Every piece is one word with its space, so joining them returns the answer exactly."""
    async with factory() as session:
        service = FoodChatService(session)
        pieces = [token.text async for token in service.answer("  밀가루 제품  ")]

    assert len(pieces) > 1
    answer = "".join(pieces)
    # The reader's own words come back, trimmed - a turn is about what they typed.
    assert answer.startswith("'밀가루 제품'")
    assert "무엇이든 물어보세요" in answer
    # No piece is empty and none has lost its space: the join is lossless.
    assert all(piece != "" for piece in pieces)
    assert answer.split(" ") == [piece.rstrip(" ") for piece in pieces]


@pytest.mark.asyncio
async def test_summarise_is_the_whole_answer_and_its_piece_count(factory) -> None:
    """The last event repeats the answer, so a client that dropped a token still has one."""
    async with factory() as session:
        service = FoodChatService(session)
        pieces = [token.text async for token in service.answer("안녕")]
        end = service.summarise(pieces)

    assert end.text == "".join(pieces)
    assert end.tokens == len(pieces)
