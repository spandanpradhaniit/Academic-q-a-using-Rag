import csv
from pathlib import Path


def load_examples(path: str) -> tuple[list[dict], list[dict]]:
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    in_scope = [r for r in rows if r.get("label") == "in_scope"]
    out_scope = [r for r in rows if r.get("label") == "out_of_scope"]
    return in_scope, out_scope


def score_threshold(in_scope_rows: list[dict], out_scope_rows: list[dict], threshold: float) -> tuple[float, float, float]:
    in_hits = sum(1 for row in in_scope_rows if float(row.get("relevance", 0.0)) >= threshold)
    out_hits = sum(1 for row in out_scope_rows if float(row.get("relevance", 0.0)) >= threshold)
    precision = in_hits / (in_hits + out_hits) if (in_hits + out_hits) else 0.0
    recall = in_hits / max(len(in_scope_rows), 1)
    f1 = 0.0 if precision + recall == 0 else (2 * precision * recall) / (precision + recall)
    return precision, recall, f1


def main() -> None:
    dataset = Path(__file__).resolve().parent.parent / "eval" / "relevance_threshold_examples.csv"
    if not dataset.exists():
        print("No calibration dataset found at", dataset)
        return
    in_scope, out_scope = load_examples(str(dataset))
    thresholds = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6]
    results = []
    for threshold in thresholds:
        precision, recall, f1 = score_threshold(in_scope, out_scope, threshold)
        results.append((threshold, precision, recall, f1))
    best = max(results, key=lambda item: item[3])
    print("threshold, precision, recall, f1")
    for row in results:
        print(row)
    print("best threshold:", best[0])


if __name__ == "__main__":
    main()
