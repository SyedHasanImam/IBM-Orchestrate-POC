from langfuse import get_client
from langfuse.langchain import CallbackHandler


def get_langfuse_handler() -> CallbackHandler:
    return CallbackHandler()


def flush_langfuse() -> None:
    get_client().flush()
