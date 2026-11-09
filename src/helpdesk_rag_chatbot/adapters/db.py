from psycopg_pool import AsyncConnectionPool

from helpdesk_rag_chatbot.config import Settings


def build_db_pool(settings: Settings) -> AsyncConnectionPool:
    """
    Build an async connection pool for the app database.

    The pool is created closed (``open=False``): the caller must ``await
    pool.open()`` at startup and ``await pool.close()`` at shutdown. Connections
    use autocommit, so each statement is committed on its own.

    :param settings: Application settings; ``app_db_url`` is the connection URL.
    :return: An unopened ``AsyncConnectionPool``.
    """
    return AsyncConnectionPool(
        conninfo=settings.app_db_url.get_secret_value(),
        open=False,
        kwargs={"autocommit": True},
    )
