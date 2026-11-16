"""Document a dev-only annotation refinement; never alter held-out test evidence."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, digest, load, now, save


if __name__ == "__main__":
    if (ROOT / "results/selection.json").exists():
        raise RuntimeError("Refinement must precede selection/test")
    cases = load(ROOT / "benchmark/cases.json")
    if any(len(q["gold"]) > 1 for q in cases):
        raise RuntimeError("Refinement already applied")
    old_frozen = load(ROOT / "benchmark/frozen_inputs.json")
    save(ROOT / "benchmark/frozen_inputs_preliminary.json", old_frozen)
    for q in cases:
        if q["id"] == "d10":
            q["gold"] += [
                {"source_id": "alice-1865", "page": 20, "evidence": "“Serpent!” screamed the Pigeon."},
                {"source_id": "alice-1865", "page": 20, "evidence": "“A likely story indeed!” said the Pigeon in a tone of the deepest contempt."}]
        if q["id"] == "d11":
            q["gold"].append({"source_id": "alice-1865", "page": 25, "evidence": "“It turned into a pig,” Alice quietly said"})
        if not q["answerable"]:
            q["absence_reason"] = "Corpus-wide concept scan and review of matching excerpts and character scenes found no requested exact datum. See benchmark/absence_audit.json; independent human confirmation pending."
            q["absence_check"] = q["absence_check"].split(";")[0] + "; all-unit scan and character-context inspection, not top-k absence alone"
    save(ROOT / "benchmark/cases.json", cases)
    frozen = {**old_frozen, "frozen_at_utc": now(), "amendment":
        "After preliminary dev retrieval and source inspection, add valid alternative evidence for dev d10 (Pigeon page20) and d11 (pig page25), and replace overbroad full-reading absence wording with actual all-unit scan/scene review. No questions, expected answers, splits or test gold changed. All final dev methods rerun on identical amended labels before model runs, selection or test.",
        "sha256": {relative: digest(ROOT / relative) for relative in old_frozen["sha256"]}}
    frozen["sha256"]["benchmark/absence_audit.json"] = digest(ROOT / "benchmark/absence_audit.json")
    save(ROOT / "benchmark/frozen_inputs.json", frozen)
    for folder in (ROOT / "results/dev").iterdir():
        for name in ("retrieval.json", "retrieval_summary.json"):
            path = folder / name
            if path.exists():
                path.rename(folder / name.replace(".json", "_preliminary.json"))
    print("Dev annotation amendment recorded; final dev retrieval must now be rerun.")
