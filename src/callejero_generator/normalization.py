"""Conservative normalization for matching Madrid street names."""

import re
import unicodedata

_PREFIXES = (
    (r"c\s*/|c\.|calle", "calle"),
    (r"av\.?|avenida", "avenida"),
    (r"p\.?\s*º|p\.?\s*o\.?|paseo", "paseo"),
    (r"gta\.?|glorieta", "glorieta"),
    (r"pl\.?|plaza", "plaza"),
    (r"ctra\.?|crt\.?|carretera", "carretera"),
)


def normalize_name(value: str) -> str:
    """Normalize spelling for lookup; never replace the canonical display string."""
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("–", "-").replace("—", "-")
    value = re.sub(r"\s+", " ", value).strip()
    for alternatives, replacement in _PREFIXES:
        value = re.sub(rf"^(?:{alternatives})(?=\s|$)", replacement, value)
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()
