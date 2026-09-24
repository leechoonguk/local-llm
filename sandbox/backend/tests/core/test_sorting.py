"""Ordering a list query: the named column first, the endpoint's own order as the tiebreak."""

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.core.sorting import ordered
from app.models.user import User


def _order_by(sort: str | None, order: str) -> str:
    """The ORDER BY clause the query compiles to, on the dialect the app runs on."""
    query = ordered(select(User), User, sort, order, User.id)
    sql = str(query.compile(dialect=postgresql.dialect()))
    return sql.split("ORDER BY", 1)[1].strip()


def test_no_sort_keeps_the_endpoints_own_order() -> None:
    """Without a sort the page is cut the way it always was."""
    assert _order_by(None, "asc") == '"user".id'


def test_sort_runs_the_named_column_then_the_tiebreak() -> None:
    """A page cut through equal values lands on the same rows twice, not two overlapping sets."""
    assert _order_by("email", "asc") == '"user".email ASC, "user".id'
    assert _order_by("created_at", "desc") == '"user".created_at DESC, "user".id'
