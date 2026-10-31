"""Review screen for both human gates.

    streamlit run review_app.py

Sidebar: start a full run from a story, or run triage & heal on existing tests.
Gate 1: edit the drafted Gherkin, then approve or reject it.
Gate 2: tick only the fixes and defects you've checked, then submit.
Everything the agent writes is committed to an ai-agent/... branch, never to main.
"""
import time

import streamlit as st
from langgraph.types import Command

from agent.graph import ROOT, app, current_branch, triage_app

st.set_page_config(page_title="AI QA Agent", layout="wide")
ss = st.session_state
ss.setdefault("step", 0)       # bumps after every decision, so widget keys never collide


def start(graph, inputs: dict) -> None:
    ss.graph = graph
    ss.config = {"configurable": {"thread_id": f"run-{time.time_ns()}"}}
    ss.step += 1
    with st.spinner("The agent is working. This can take a few minutes..."):
        ss.result = graph.invoke(inputs, ss.config)


def resume(answer: dict) -> None:
    ss.step += 1
    with st.spinner("The agent is working. This can take a few minutes..."):
        ss.result = ss.graph.invoke(Command(resume=answer), ss.config)


# ---------------------------------------------------------------------------
# Sidebar: what to run
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Run")
    mode = st.radio("What to run", ["Full run from a story", "Triage & heal existing tests"])
    if mode == "Full run from a story":
        stories = sorted((ROOT / "stories").glob("*.md"))
        story = st.selectbox("Story", stories, format_func=lambda p: p.name)
        if st.button("Start", type="primary", disabled=not stories):
            start(app, {"story_name": story.stem, "story": story.read_text()})
    else:
        keyword = st.text_input("Only tests matching (pytest -k), optional")
        if st.button("Run tests and triage", type="primary"):
            start(triage_app, {"keyword": keyword.strip()})
    st.divider()
    st.caption(f"Git branch: **{current_branch() or 'not a git repository'}**")


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------
def gate_1(payload: dict) -> None:
    st.header("Gate 1: review the drafted scenarios")
    st.write("Edit, delete or keep scenarios. Nothing is generated or run until you approve. "
             "Replace any `[NEEDS DATA: ...]` with the real value, or delete that scenario.")
    text = st.text_area("Gherkin", payload["scenarios"], height=520, key=f"g1-{ss.step}")
    if "[NEEDS DATA" in text:
        st.warning("Some scenarios still contain [NEEDS DATA]. Their tests will fail until filled in.")
    left, right = st.columns(2)
    if left.button("Approve and generate tests", type="primary", key=f"g1a-{ss.step}"):
        resume({"approved_text": text})
        st.rerun()
    if right.button("Reject all", key=f"g1r-{ss.step}"):
        resume({"approved_text": ""})
        st.rerun()


def gate_2(payload: dict) -> None:
    st.header("Gate 2: review proposed fixes and defects")
    st.write("Tick only what you've checked. Low confidence, or a reason that says it can't "
             "confirm the cause, means reject. Approved items are committed to the agent branch.")
    with st.form(f"g2-{ss.step}"):
        picks = []
        for i, p in enumerate(payload["proposals"]):
            with st.container(border=True):
                st.subheader(f"[{i}] {p['test'].split('::')[-1]}")
                if p.get("same_error"):
                    with st.expander(f"+ {len(p['same_error'])} more test(s) with the same error"):
                        st.write("\n".join(f"- {t.split('::')[-1]}" for t in p["same_error"]))
                st.markdown(f"**Triage:** `{p['category']}` · confidence **{p['confidence']:.2f}**")
                if p["confidence"] < 0.7:
                    st.warning("Low confidence: check this carefully before approving.")
                st.write(p["reason"])
                st.caption(f"Evidence: {p['evidence']}")

                if p["action"] == "fix_test":
                    st.code(p["diff"], language="diff")
                    label = "Approve this fix"
                elif p["action"] == "file_defect":
                    with st.expander("Draft defect report", expanded=True):
                        st.markdown(p["defect"])
                    label = "Approve and save this defect"
                elif p["action"] == "rerun":
                    st.write("Proposed action: rerun (looks flaky).")
                    label = "Approve rerun"
                else:
                    st.info("No concrete fix proposed. Nothing to approve; investigate by hand.")
                    continue
                if st.checkbox(label, key=f"g2-{ss.step}-{i}"):
                    picks.append(i)
        submitted = st.form_submit_button("Submit decisions", type="primary")
    if submitted:
        resume({"approved_ids": picks})
        st.rerun()


def done(result: dict) -> None:
    st.header("Run finished")
    if result.get("collect_ok") is False:
        st.error("The generated code did not load.")
        st.code(result.get("collect_error", ""))
    failures = result.get("failures", [])
    if failures:
        st.warning(f"{len(failures)} test(s) still failing")
        for f in failures:
            st.write(f"- {f['test'].split('::')[-1]}")
    elif "failures" in result:
        st.success("All tests pass.")
    branch = result.get("branch") or current_branch()
    if branch and branch.startswith("ai-agent/"):
        st.info(f"The agent's changes are committed on **{branch}**. Review them, then push "
                f"and open a pull request:\n\n`git push -u origin {branch}`")


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title("AI QA Agent")
result = ss.get("result")
if result is None:
    st.info("Choose what to run in the sidebar.")
elif "__interrupt__" in result:
    payload = result["__interrupt__"][0].value
    gate_1(payload) if payload["gate"] == 1 else gate_2(payload)
else:
    done(result)
