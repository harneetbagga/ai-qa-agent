"""Run only the triage and heal part of the agent, on tests that already exist.

    python triage_heal.py                      run all tests, then triage the failures
    python triage_heal.py -k cart              only tests whose name matches "cart"
    python triage_heal.py tests/steps/test_add_to_cart.py
    python triage_heal.py --last               triage the last run's results.xml, no rerun

Same flow as the full agent from the test run onward:
run tests -> triage -> gate 2 (you approve) -> apply approved fixes -> rerun,
for up to MAX_HEAL_ROUNDS rounds.
"""
import argparse

from agent.graph import (MAX_HEAL_ROUNDS, RESULTS, ROOT, apply_fixes, parse_junit,
                         run_pytest, tail, triage)
from run import gate_2


def run(targets: list[str], keyword: str | None) -> list[dict]:
    if RESULTS.exists():
        RESULTS.unlink()
    args = [*(targets or ["tests"]), f"--junitxml={RESULTS.name}",
            "--tracing=retain-on-failure", "--screenshot=only-on-failure"]
    if keyword:
        args += ["-k", keyword]
    result = run_pytest(*args)
    if not RESULTS.exists():
        print("pytest did not produce results:\n" + tail(result.stdout + result.stderr))
        return []
    return parse_junit(RESULTS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("targets", nargs="*", help="test files or folders (default: tests)")
    parser.add_argument("-k", dest="keyword", help="only tests matching this pytest -k expression")
    parser.add_argument("--last", action="store_true",
                        help="use the existing results.xml instead of running the tests")
    args = parser.parse_args()

    if args.last:
        if not RESULTS.exists():
            raise SystemExit(f"No {RESULTS.relative_to(ROOT)} yet. Run without --last first.")
        failures = parse_junit(RESULTS)
    else:
        failures = run(args.targets, args.keyword)

    for round_no in range(1, MAX_HEAL_ROUNDS + 1):
        if not failures:
            print("\nAll selected tests pass.")
            return
        print(f"\nRound {round_no}: {len(failures)} failing test(s). Triaging...")
        proposals = triage({"failures": failures})["proposals"]
        approved_ids = set(gate_2({"proposals": proposals})["approved_ids"])
        approved = [p for i, p in enumerate(proposals) if i in approved_ids]
        if not apply_fixes({"proposals": approved})["fixes_applied"]:
            print("\nNo fixes applied, so not rerunning.")
            break
        failures = run(args.targets, args.keyword)

    print(f"\nRemaining failures: {len(failures)}")
    for f in failures:
        print(" -", f["test"])


if __name__ == "__main__":
    main()
