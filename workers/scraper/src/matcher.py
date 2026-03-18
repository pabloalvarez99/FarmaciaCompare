from dataclasses import dataclass
from rapidfuzz import process, fuzz
from unidecode import unidecode
import re


def normalize_for_matching(text: str) -> str:
    text = text.lower().strip()
    text = unidecode(text)
    text = re.sub(r"[^\w\s/]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


@dataclass
class MatchResult:
    medication_id: str
    matched_name: str
    confidence: float


class DrugMatcher:
    THRESHOLD = 75.0
    AUTO_LINK_THRESHOLD = 85.0

    def __init__(self, candidates: list[dict]):
        self.candidates = candidates
        self.names = [c["normalized_name"] for c in candidates]

    def match(self, raw_name: str) -> MatchResult | None:
        if not raw_name or not self.names:
            return None
        normalized = normalize_for_matching(raw_name)
        results = process.extract(normalized, self.names, scorer=fuzz.WRatio, limit=3)
        if not results:
            return None
        best_name, best_score, best_idx = results[0]
        if best_score < self.THRESHOLD:
            return None
        medication_id = self.candidates[best_idx]["medication_id"]
        return MatchResult(medication_id=medication_id, matched_name=best_name, confidence=best_score / 100.0)

    def match_all(self, raw_names: list[str]) -> dict[str, MatchResult | None]:
        return {name: self.match(name) for name in raw_names}
