"""Pure helpers for the sidebar's chat list: grouping, short titles, ages."""

from datetime import UTC, datetime

from helpdesk_rag_chatbot.ui.backend import SessionInfo

# Show the search box only when the list is long enough to need it.
SEARCH_MIN_CHATS = 8


def short(title: str, limit: int = 22) -> str:
    """Cut a title to ``limit`` characters, ending with an ellipsis if cut."""
    return title if len(title) <= limit else title[: limit - 1] + "…"


def ago(moment: datetime, now: datetime | None = None) -> str:
    """A compact age: ``5 min``, ``3 h`` or ``2 d`` (at least ``1 min``)."""
    seconds = ((now or datetime.now(UTC)) - moment).total_seconds()
    if seconds < 3600:
        return f"{max(int(seconds // 60), 1)} min"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h"
    return f"{int(seconds // 86400)} d"


def group_by_day(
    sessions: list[SessionInfo], now: datetime | None = None
) -> list[tuple[str, list[SessionInfo]]]:
    """
    Group sessions under Today, Yesterday, Previous 7 days and Older.

    Days are calendar days in the viewer's local time. Order inside a group,
    and the order of the groups, follow the input (newest first); a group with
    no sessions is left out.
    """
    today = (now or datetime.now()).astimezone().date()
    groups: dict[str, list[SessionInfo]] = {}
    for session in sessions:
        age = (today - session.updated_at.astimezone().date()).days
        if age <= 0:
            label = "Today"
        elif age == 1:
            label = "Yesterday"
        elif age <= 7:
            label = "Previous 7 days"
        else:
            label = "Older"
        groups.setdefault(label, []).append(session)
    return list(groups.items())
