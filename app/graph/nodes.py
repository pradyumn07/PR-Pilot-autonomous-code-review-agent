import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from .state import PRReviewState, ASTFinding, SemgrepFinding, LLMReview, ReviewComment
import json

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2
)


async def load_pr_state(state: PRReviewState) -> dict:
    from app.github_client import get_pr_diff, get_pr_files

    print(f"Loading PR #{state['pr_number']} from {state['repo']}")

    diff = get_pr_diff(state["repo"], state["pr_number"])
    files_data = get_pr_files(state["repo"], state["pr_number"])

    changed_files = [
        {
            "filename": f["filename"],
            "patch": f.get("patch", ""),
            "additions": f["additions"],
            "deletions": f["deletions"]
        }
        for f in files_data
    ]

    return {
        "diff": diff,
        "changed_files": changed_files,
        "ast_findings": [],
        "semgrep_findings": [],
        "confidence_score": 0.0,
        "final_comments": [],
        "should_post": False,
        "error": None
    }


async def ast_parse_node(state: PRReviewState) -> dict:
    print("Running AST parser...")
    findings = []

    for file in state["changed_files"]:
        if not file["filename"].endswith(".py"):
            continue
        if not file.get("patch"):
            continue

        findings.append({
            "filename": file["filename"],
            "function_name": "changed_code",
            "signature": f"File: {file['filename']}",
            "has_docstring": False,
            "complexity": file["additions"] + file["deletions"]
        })

    return {"ast_findings": findings}


async def semgrep_scan_node(state: PRReviewState) -> dict:
    print("Running Semgrep scan...")
    # Stub for now — Docker sandbox comes in Day 3
    return {"semgrep_findings": []}


async def llm_review_node(state: PRReviewState) -> dict:
    print("Running LLM review...")

    if not state.get("diff"):
        return {"llm_review": None}

    # Stage 1 — understand intent
    intent_messages = [
        SystemMessage(content="You are a senior software engineer reviewing a pull request. Summarize what this PR is trying to do in one sentence."),
        HumanMessage(content=f"PR Diff:\n{state['diff'][:3000]}")
    ]

    intent_response = await llm.ainvoke(intent_messages)
    intent_summary = intent_response.content

    # Stage 2 — generate review comments
    review_messages = [
        SystemMessage(content="""You are a senior software engineer doing a code review.
Analyze the diff and return a JSON object with this exact structure:
{
  "comments": [
    {
      "file": "filename.py",
      "line": 10,
      "severity": "critical|major|minor|nit",
      "category": "security|correctness|performance|style",
      "message": "what the issue is",
      "suggestion": "how to fix it",
      "confidence": 0.9
    }
  ],
  "overall_confidence": 0.85
}
Return ONLY the JSON. No explanation. No markdown."""),
        HumanMessage(content=f"""PR Intent: {intent_summary}

Diff:
{state['diff'][:4000]}

AST findings:
{json.dumps(state.get('ast_findings', []), indent=2)}""")
    ]

    review_response = await llm.ainvoke(review_messages)

    try:
        raw = review_response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

        comments = [ReviewComment(**c) for c in data.get("comments", [])]
        llm_review = LLMReview(
            intent_summary=intent_summary,
            comments=comments,
            overall_confidence=data.get("overall_confidence", 0.5)
        )
    except Exception as e:
        print(f"LLM parse error: {e}")
        llm_review = LLMReview(
            intent_summary=intent_summary,
            comments=[],
            overall_confidence=0.3
        )

    return {"llm_review": llm_review}


async def synthesize_review_node(state: PRReviewState) -> dict:
    print("Synthesizing review...")

    llm_review = state.get("llm_review")
    if not llm_review:
        return {
            "confidence_score": 0.0,
            "final_comments": [],
            "should_post": False
        }

    confidence = llm_review.overall_confidence
    comments = llm_review.comments

    should_post = confidence >= 0.7

    return {
        "confidence_score": confidence,
        "final_comments": comments,
        "should_post": should_post
    }


async def post_review_node(state: PRReviewState) -> dict:
    print("Posting review to GitHub...")
    from app.github_client import post_review_comment

    comments = state.get("final_comments", [])
    llm_review = state.get("llm_review")
    intent = llm_review.intent_summary if llm_review else "No summary"

    if not comments:
        body = f"## PR Pilot Review\n\n**Intent:** {intent}\n\n✅ No issues found."
    else:
        critical = [c for c in comments if c.severity == "critical"]
        major = [c for c in comments if c.severity == "major"]
        minor = [c for c in comments if c.severity == "minor"]
        nits = [c for c in comments if c.severity == "nit"]

        body = f"## PR Pilot Review 🤖\n\n"
        body += f"**Intent:** {intent}\n\n"
        body += f"**Confidence:** {state['confidence_score']:.0%}\n\n"
        body += f"### Summary\n"
        body += f"- 🔴 Critical: {len(critical)}\n"
        body += f"- 🟠 Major: {len(major)}\n"
        body += f"- 🟡 Minor: {len(minor)}\n"
        body += f"- 💬 Nits: {len(nits)}\n\n"

        if critical or major:
            body += "### Issues\n"
            for c in critical + major:
                body += f"\n**[{c.severity.upper()}] {c.file} (line {c.line})**\n"
                body += f"{c.message}\n"
                body += f"💡 *{c.suggestion}*\n"

    post_review_comment(state["repo"], state["pr_number"], body)
    return {}


async def request_human_node(state: PRReviewState) -> dict:
    print(f"Low confidence ({state['confidence_score']:.0%}) — flagging for human review")
    from app.github_client import post_review_comment

    body = (
        f"## PR Pilot Review 🤖\n\n"
        f"⚠️ Confidence too low ({state['confidence_score']:.0%}) for auto-review.\n"
        f"A human reviewer has been requested."
    )
    post_review_comment(state["repo"], state["pr_number"], body)
    return {}


async def generate_tests_node(state: PRReviewState) -> dict:
    print("Generating tests...")
    # Full implementation comes Day 3
    return {}