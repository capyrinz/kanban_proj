"""Проверка требований лабораторной работы к покрытию кода.

Пороги: >= 80% операторов, >= 70% ветвлений.
Использование: python check_coverage.py [path/to/coverage.json]
"""
import json
import sys

MIN_LINES = 80.0
MIN_BRANCHES = 70.0


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "coverage.json"
    with open(path, encoding="utf8") as handle:
        totals = json.load(handle)["totals"]

    lines = totals["percent_statements_covered"]
    branches = totals["percent_branches_covered"]
    print(f"Coverage: {lines:.1f}% statements, {branches:.1f}% branches")

    failed = False
    if lines < MIN_LINES:
        print(f"FAIL: statements coverage {lines:.1f}% < {MIN_LINES}%", file=sys.stderr)
        failed = True
    if branches < MIN_BRANCHES:
        print(f"FAIL: branch coverage {branches:.1f}% < {MIN_BRANCHES}%", file=sys.stderr)
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
