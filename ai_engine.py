import anthropic
from config import ANTHROPIC_API_KEY

try:
    from duckduckgo_search import DDGS
    _ddgs_available = True
except ImportError:
    _ddgs_available = False

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = (
    "You are a screen assistant. The user has shared a screenshot of their screen "
    "along with their cursor coordinates (x, y pixels). "
    "Identify what is at or near the cursor and answer the user's question with "
    "clear, numbered steps suitable for beginners. Be concise. "
    "Use the web_search tool only when you genuinely need external documentation "
    "(e.g. software-specific how-to guides, API references)."
)

WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": "Search the web for documentation, how-to guides, or software help.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."}
        },
        "required": ["query"],
    },
}


def _web_search(query: str) -> str:
    if not _ddgs_available:
        return "Web search unavailable (duckduckgo-search not installed)."
    try:
        with DDGS() as ddgs:
            hits = list(ddgs.text(query, max_results=3))
        if not hits:
            return "No results found."
        parts = [f"**{h['title']}**\n{h['body']}\nSource: {h['href']}" for h in hits]
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        return f"Search failed: {e}"


def ask_claude(b64_image: str, cursor_x: int, cursor_y: int,
               screen_w: int, screen_h: int, question: str) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64_image,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        f"Screen size: {screen_w}x{screen_h}. "
                        f"Cursor position: ({cursor_x}, {cursor_y}).\n\n"
                        f"User question: {question}"
                    ),
                },
            ],
        }
    ]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=[WEB_SEARCH_TOOL],
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "No response generated."

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "web_search":
                    result = _web_search(block.input.get("query", ""))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            return f"Unexpected stop reason: {response.stop_reason}"
