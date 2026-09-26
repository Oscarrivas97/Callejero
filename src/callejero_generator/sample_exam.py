"""Read the supplied exam as an unscored style and regression fixture."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class ExamQuestion:
    number: int
    page: int
    prompt: str
    options: dict[str, str]
    components: dict[str, list[str]]
    mentions_emergency: bool


_QUESTION = re.compile(r"^\s*(\d{1,2})\.\s+(.+)$")
_OPTION = re.compile(r"^\s*([abc])\)\s+(.+)$", re.IGNORECASE)
_SEPARATOR = re.compile(r"\s+[-–—]{1,2}\s+")


def split_components(text: str) -> list[str]:
    """Heuristic split for style metrics; raw option text remains authoritative."""
    return [part.strip() for part in _SEPARATOR.split(text) if part.strip()]


def extract_exam(path: str | Path) -> list[ExamQuestion]:
    raw: list[dict] = []
    current: dict | None = None
    field: str | None = None
    with pdfplumber.open(path) as document:
        for page_number, page in enumerate(document.pages, 1):
            if page_number == 1:
                continue  # cover/instructions
            for line in (page.extract_text() or "").splitlines():
                line = line.strip()
                if not line or line.startswith(("SIMULACRO CALLEJERO", "Página ")) or "WWW.ELHIDRANTE.ES" in line:
                    continue
                question = _QUESTION.match(line)
                option = _OPTION.match(line)
                if question:
                    current = {"number": int(question[1]), "page": page_number,
                               "prompt": question[2], "options": {}}
                    raw.append(current)
                    field = "prompt"
                elif option:
                    if current is None:
                        raise ValueError(f"Option before question on page {page_number}")
                    letter = option[1].upper()
                    if letter in current["options"]:
                        raise ValueError(f"Duplicate option {letter} in question {current['number']}")
                    current["options"][letter] = option[2]
                    field = letter
                elif current is not None and field == "prompt":
                    current["prompt"] += " " + line
                elif current is not None and field is not None:
                    current["options"][field] += " " + line
    if [item["number"] for item in raw] != list(range(1, 31)):
        raise ValueError("Expected the 30 numbered sample-exam questions")
    result: list[ExamQuestion] = []
    for item in raw:
        if set(item["options"]) != {"A", "B", "C"}:
            raise ValueError(f"Question {item['number']} does not have A/B/C options")
        prompt = " ".join(item["prompt"].split())
        options = {key: " ".join(value.split()) for key, value in item["options"].items()}
        result.append(ExamQuestion(
            item["number"], item["page"], prompt, options,
            {key: split_components(value) for key, value in options.items()},
            bool(re.search(r"emergencia|prioritari|rotativos", prompt, re.IGNORECASE)),
        ))
    return result


def write_exam_fixture(path: str | Path, destination: str | Path) -> int:
    questions = extract_exam(path)
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([asdict(q) for q in questions], ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return len(questions)
