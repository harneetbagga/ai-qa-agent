"""Run the agent from the terminal, one story at a time.

    python run.py stories/add_to_cart.md

Gate 1: the drafted scenarios are saved to review/<story>.feature. Edit or delete
        scenarios there in VS Code, save, then press Enter here. Type 'reject' to stop.
Gate 2: each proposed fix or defect is shown; answer y or n.

(The Streamlit review screen can replace these two functions later.)
"""
import sys
from pathlib import Path

from langgraph.types import Command

from agent.graph import ROOT, app

REVIEW = ROOT / "review"


def gate_1(payload: dict) -> dict:
    REVIEW.mkdir(exist_ok=True)
    draft = REVIEW / f"{payload['story_name']}.feature"
    draft.write_text(payload["scenarios"] + "\n")
    print(f"\nGATE 1: review the drafted scenarios in {draft.relative_to(ROOT)}")
    print("Edit or delete scenarios, save the file, then press Enter (or type 'reject').")
    if input("> ").strip().lower() == "reject":
        return {"approved_text": ""}
    return {"approved_text": draft.read_text()}


def gate_2(payload: dict) -> dict:
    approved = []
    for i, p in enumerate(payload["proposals"]):
        print("\n" + "=" * 70)
        print(f"[{i}] {p['test']}")
        if p.get("same_error"):
            print(f"    + {len(p['same_error'])} more test(s) with the same error")
        print(f"Triage: {p['category']} (confidence {p['confidence']:.2f})")
        print(f"Reason: {p['reason']}\nEvidence: {p['evidence']}")
        if p["action"] == "none":
            print("\nNo concrete fix proposed. Nothing to approve; investigate by hand.")
            continue
        if p["action"] == "fix_test":
            print("\nProposed fix:\n" + p["diff"])
        elif p["action"] == "file_defect":
            print("\nDraft defect:\n" + p["defect"])
        else:
            print("\nProposed action: rerun (flaky)")
        if input("Approve? [y/N] ").strip().lower() == "y":
            approved.append(i)
    return {"approved_ids": approved}


def main(story_file: str) -> None:
    path = Path(story_file)
    name = path.stem
    config = {"configurable": {"thread_id": name}}
    result = app.invoke({"story_name": name, "story": path.read_text()}, config)

    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        answer = gate_1(payload) if payload["gate"] == 1 else gate_2(payload)
        result = app.invoke(Command(resume=answer), config)

    print("\nDone.")
    if result.get("collect_ok") is False:
        print("Generated code did not load:\n" + result.get("collect_error", ""))
    failures = result.get("failures", [])
    print(f"Remaining failures: {len(failures)}")
    for f in failures:
        print(" -", f["test"])
    branch = result.get("branch")
    if branch:
        print(f"\nChanges are committed on branch {branch} (main is untouched).")
        print(f"Review with: git log main..{branch}   then: git push -u origin {branch}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python run.py stories/<story>.md")
    main(sys.argv[1])
