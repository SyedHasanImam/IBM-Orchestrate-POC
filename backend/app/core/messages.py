def extract_text(message) -> str:
    """Return the plain text of a LangChain message, regardless of whether
    `.content` is a plain string or a list of content blocks (as some Gemini
    models return, each block a dict with a 'text' field)."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "") for block in content if isinstance(block, dict)
    )
