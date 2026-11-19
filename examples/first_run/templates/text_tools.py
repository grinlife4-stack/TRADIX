"""Small dependency-free text utilities produced by the first-run fixture."""
import re
import unicodedata


def slugify(value: str) -> str:
    """Convert text to a lowercase, ASCII, hyphen-separated URL slug."""
    if not isinstance(value, str):
        raise TypeError("value must be a string")

    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    words = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    return re.sub(r"-+", "-", words).strip("-")
