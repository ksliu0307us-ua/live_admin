"""Text preprocessing for email/receipt input."""

import re


def preprocess_text(text: str) -> str:
    """Clean and normalize input text for LLM extraction."""
    text = re.sub(r"<[^>]+>", " ", text)

    text = re.sub(r"https?://\S+", "[URL]", text)

    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    text = text.strip()

    max_chars = 15000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Text truncated]"

    return text
