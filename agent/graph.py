"""AI QA agent.

Flow: story -> plan (Gherkin) -> human gate 1 -> generate (pytest-bdd + Playwright)
      -> run tests -> triage failures -> human gate 2 -> apply approved fixes -> run again.

Nothing the model writes reaches a test run without gate 1, and no fix or defect
is applied or filed without gate 2.
"""
import difflib
import hashlib
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
FEATURES = ROOT / "features"
STEPS = ROOT / "tests" / "steps"
PAGES = ROOT / "pages"
DEFECTS = ROOT / "defects"
RESULTS = ROOT / "results.xml"

MAX_HEAL_ROUNDS = 2      # stops the run -> triage -> fix loop from going on forever
MAX_LOG_CHARS = 4000     # keep error output short enough to send to the model
EDITABLE = ("pages/", "tests/steps/")  # the only folders the model may write to


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class QAState(TypedDict, total=False):
    story_name: str          # file name of the story, e.g. "add_to_cart"
    story: str               # the story text
    scenarios: str           # Gherkin drafted by the planner
    approved: str            # Gherkin after your review at gate 1
    files_written: list[str]
    collect_ok: bool
    collect_error: str
    failures: list[dict]
    proposals: list[dict]
    heal_rounds: int
    fixes_applied: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@lru_cache
def llm():
    # e.g. QA_AGENT_MODEL=anthropic:<model id>  or  openai:<model id>
    # No temperature setting: newer models reject it and choose their own.
    return init_chat_model(os.environ["QA_AGENT_MODEL"])


def ask(text: str) -> str:
    """Send a prompt, return plain text."""
    content = llm().invoke(text).content
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


def prompt(name: str, **values) -> str:
    """Fill a template from prompts/<name>.md. Templates must not contain literal braces."""
    return (ROOT / "prompts" / f"{name}.md").read_text().format(**values)


def tail(text: str, limit: int = MAX_LOG_CHARS) -> str:
    return text if len(text) <= limit else "...\n" + text[-limit:]


def read_folder(folder: Path, pattern: str = "*.py") -> str:
    files = [p for p in sorted(folder.glob(pattern)) if p.name != "__init__.py"]
    if not files:
        return "(none yet)"
    return "\n\n".join(f"### {p.relative_to(ROOT)}\n{p.read_text()}" for p in files)


def conventions() -> str:
    for name in ("CLAUDE.md", ".github/copilot-instructions.md"):
        path = ROOT / name
        if path.exists():
            return path.read_text()
    return "(no conventions file)"


def run_pytest(*args: str) -> subprocess.CompletedProcess:
    # sys.executable = the Python of your virtual environment, so the right pytest runs
    return subprocess.run([sys.executable, "-m", "pytest", *args],
                          cwd=ROOT, capture_output=True, text=True)


# Lenient on purpose: models vary the header ("### FILE:", "**FILE:**", `path` in backticks)
# and may leave a blank line before the code fence.
FILE_BLOCK = re.compile(
    r"^[#*\s]*FILE:?[*\s]*`?([\w./-]+\.py)`?[*\s]*\n+\s*```[\w-]*\n(.*?)^\s*```",
    re.S | re.M | re.I,
)


def parse_files(text: str) -> dict[str, str]:
    """Read '### FILE: path' + fenced code blocks from a model answer.
    Only paths inside EDITABLE folders are accepted."""
    files = {}
    for path, body in FILE_BLOCK.findall(text):
        if path.startswith(EDITABLE) and ".." not in path and path.endswith(".py"):
            files[path] = body
    return files


def write_files(files: dict[str, str]) -> list[str]:
    for path, body in files.items():
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    return list(files)


def make_diff(files: dict[str, str]) -> str:
    out = []
    for path, new in files.items():
        target = ROOT / path
        old = target.read_text() if target.exists() else ""
        out.extend(difflib.unified_diff(
            old.splitlines(keepends=True), new.splitlines(keepends=True),
            fromfile=f"a/{path}", tofile=f"b/{path}"))
    return "".join(out)


def classname_to_file(classname: str) -> str:
    # junit classname "tests.steps.test_cart" -> "tests/steps/test_cart.py"
    return classname.replace(".", "/") + ".py" if classname else ""


def parse_junit(path: Path) -> list[dict]:
    failures = []
    for case in ET.parse(path).getroot().iter("testcase"):
        for kind in ("failure", "error"):
            node = case.find(kind)
            if node is not None:
                classname = case.get("classname", "")
                file = classname_to_file(classname)
                failures.append({
                    "test": f"{classname}::{case.get('name')}",
                    "nodeid": f"{file}::{case.get('name')}",
                    "file": file,
                    "kind": kind,
                    "message": node.get("message", ""),
                    "details": tail(node.text or ""),
                })
                break
    return failures


def strip_fences(text: str) -> str:
    """Remove a Markdown code fence (```gherkin ... ```) around the model's answer,
    so the .feature file starts with the Feature line."""
    text = text.strip()
    match = re.search(r"```[\w-]*\s*\n(.*?)\n\s*```", text, re.S)
    if match:
        text = match.group(1)
    else:  # an opening fence with no closing one, or a stray closing fence
        text = re.sub(r"^```[\w-]*\s*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:80]


SNAPSHOTS = ROOT / "test-results" / "dom"
MAX_SNAPSHOT_CHARS = 8000


def page_snapshot(nodeid: str) -> str:
    """The URL and HTML saved by tests/conftest.py when this test failed."""
    path = SNAPSHOTS / (hashlib.md5(nodeid.encode()).hexdigest()[:16] + ".txt")
    if not path.exists():
        return "(no page snapshot saved)"
    return path.read_text()[:MAX_SNAPSHOT_CHARS]


def feature_for(test_file: str) -> str:
    """tests/steps/test_add_to_cart.py -> the text of features/add_to_cart.feature."""
    name = Path(test_file).stem.removeprefix("test_")
    path = FEATURES / f"{name}.feature"
    return path.read_text() if path.exists() else "(feature file not found)"


def signature(failure: dict) -> str:
    """Failures with the same error, ignoring quoted values such as product names,
    probably share one root cause, so they are triaged once as a group."""
    text = failure["message"] or failure["details"][-300:]
    text = re.sub(r"\"[^\"]*\"|'[^']*'", "…", text)
    text = re.sub(r"\d+", "N", text)
    return f"{failure['file']}|{text[:300]}"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def plan(state: QAState) -> dict:
    return {"scenarios": strip_fences(ask(prompt("plan", story=state["story"])))}


def human_gate_1(state: QAState) -> dict:
    decision = interrupt({"gate": 1, "story_name": state["story_name"],
                          "scenarios": state["scenarios"]})
    # strip_fences again in case a fence was left in the reviewed file
    return {"approved": strip_fences(decision.get("approved_text") or "")}


def generate(state: QAState) -> dict:
    """Write the approved feature, ask the model for step definitions (and any
    missing page-object methods), then check the code at least loads."""
    name = state["story_name"]
    feature = FEATURES / f"{name}.feature"
    feature.parent.mkdir(parents=True, exist_ok=True)
    feature.write_text(state["approved"] + "\n")
    step_path = f"tests/steps/test_{name}.py"

    request = prompt(
        "generate",
        feature_name=feature.name,
        feature=state["approved"],
        step_path=step_path,
        pages=read_folder(PAGES),
        conventions=conventions(),
    )
    feedback, error = "", ""
    debug = ROOT / "review"
    debug.mkdir(exist_ok=True)
    for attempt in range(1, 3):  # one retry if the first attempt doesn't load
        answer = ask(request + feedback)
        # Keep the raw answer so you can see exactly what the model returned
        (debug / f"{name}_generate_attempt{attempt}.md").write_text(answer)
        files = parse_files(answer)
        if step_path not in files:
            found = ", ".join(files) or "no files in the expected format"
            error = (f"The answer did not contain {step_path} (found: {found}). "
                     f"Raw answer saved to review/{name}_generate_attempt{attempt}.md")
        else:
            write_files(files)
            check = run_pytest(step_path, "--collect-only", "-q")
            if check.returncode == 0:
                return {"files_written": list(files), "collect_ok": True, "collect_error": ""}
            error = tail(check.stdout + check.stderr)
        feedback = (
            "\n\nYour previous answer failed. Error:\n" + error +
            "\n\nFix it and output every file again in the same format."
        )
    return {"collect_ok": False, "collect_error": error}


def run_tests(state: QAState) -> dict:
    if RESULTS.exists():
        RESULTS.unlink()
    result = run_pytest(
        "tests",
        f"--junitxml={RESULTS.name}",
        "--tracing=retain-on-failure",       # Playwright trace for each failure
        "--screenshot=only-on-failure",
    )
    if not RESULTS.exists():  # pytest crashed before writing results
        return {"failures": [{"test": "pytest", "file": "", "kind": "error",
                              "message": "pytest did not produce results",
                              "details": tail(result.stdout + result.stderr)}]}
    return {"failures": parse_junit(RESULTS)}


class Triage(BaseModel):
    category: Literal["app_bug", "test_bug", "flaky"]
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(description="One or two sentences on why")
    evidence: str = Field(description="The line of the error or code that shows it")


def triage(state: QAState) -> dict:
    classifier = llm().with_structured_output(Triage)
    pages = read_folder(PAGES)

    # Group failures that share an error: 14 tests failing the same way is one problem.
    groups: dict[str, list[dict]] = {}
    for failure in state.get("failures", []):
        groups.setdefault(signature(failure), []).append(failure)

    proposals = []
    for members in groups.values():
        failure = members[0]
        test_file = ROOT / failure["file"] if failure["file"] else None
        test_code = test_file.read_text() if test_file and test_file.exists() else "(not found)"
        others = [m["test"] for m in members[1:]]
        shared = dict(
            test=failure["test"], message=failure["message"], details=failure["details"],
            test_code=test_code, pages=pages,
            # From the full run: the approved Gherkin. Run alone: read the feature file.
            feature=state.get("approved") or feature_for(failure["file"]),
            snapshot=page_snapshot(failure.get("nodeid", "")),
            others="\n".join(others) or "(none)",
        )

        verdict = classifier.invoke(prompt("triage", **shared))
        proposal = {**failure, **verdict.model_dump(), "same_error": others}

        if verdict.category == "test_bug":
            files = parse_files(ask(prompt("heal", reason=verdict.reason,
                                           conventions=conventions(), **shared)))
            if files and make_diff(files):
                proposal["action"] = "fix_test"
                proposal["changes"] = files
                proposal["diff"] = make_diff(files)
            else:
                # Nothing concrete to approve: show it, but don't ask for a decision.
                proposal["action"] = "none"
        elif verdict.category == "app_bug":
            proposal["action"] = "file_defect"
            proposal["defect"] = ask(prompt("defect", reason=verdict.reason, **shared)).strip()
        else:
            proposal["action"] = "rerun"   # flaky: no code change, just run again
        proposals.append(proposal)
    return {"proposals": proposals}


def human_gate_2(state: QAState) -> dict:
    decision = interrupt({"gate": 2, "proposals": state["proposals"]})
    approved_ids = set(decision.get("approved_ids", []))
    approved = [p for i, p in enumerate(state["proposals"]) if i in approved_ids]
    return {"proposals": approved, "heal_rounds": state.get("heal_rounds", 0) + 1}


def apply_fixes(state: QAState) -> dict:
    """Apply only what you approved at gate 2."""
    applied = 0
    touched: set[str] = set()
    DEFECTS.mkdir(exist_ok=True)
    for p in state.get("proposals", []):
        if p["action"] == "fix_test" and p.get("changes"):
            # Each proposal rewrites whole files, so two fixes to one file would
            # overwrite each other. Apply the first; the rest wait for the next round.
            if touched & set(p["changes"]):
                print(f"Skipped (same file already changed this round): {p['test']}")
                continue
            write_files(p["changes"])
            touched |= set(p["changes"])
            applied += 1
        elif p["action"] == "file_defect":
            (DEFECTS / f"{slug(p['test'])}.md").write_text(p["defect"] + "\n")
        elif p["action"] == "rerun":
            applied += 1   # a rerun is worth it for flaky tests
    return {"fixes_applied": applied}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def after_gate_1(state: QAState) -> str:
    return "generate" if state.get("approved") else END        # rejected everything


def after_generate(state: QAState) -> str:
    return "run_tests" if state.get("collect_ok") else END       # code didn't load


def after_run(state: QAState) -> str:
    if state.get("failures") and state.get("heal_rounds", 0) < MAX_HEAL_ROUNDS:
        return "triage"
    return END


def after_apply(state: QAState) -> str:
    return "run_tests" if state.get("fixes_applied") else END    # only defects filed


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
g = StateGraph(QAState)
for name, fn in [("plan", plan), ("human_gate_1", human_gate_1), ("generate", generate),
                 ("run_tests", run_tests), ("triage", triage),
                 ("human_gate_2", human_gate_2), ("apply_fixes", apply_fixes)]:
    g.add_node(name, fn)

g.add_edge(START, "plan")
g.add_edge("plan", "human_gate_1")
g.add_conditional_edges("human_gate_1", after_gate_1, ["generate", END])
g.add_conditional_edges("generate", after_generate, ["run_tests", END])
g.add_conditional_edges("run_tests", after_run, ["triage", END])
g.add_edge("triage", "human_gate_2")
g.add_edge("human_gate_2", "apply_fixes")
g.add_conditional_edges("apply_fixes", after_apply, ["run_tests", END])

app = g.compile(checkpointer=InMemorySaver())
