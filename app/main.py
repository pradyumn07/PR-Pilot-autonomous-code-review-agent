import os
import hmac
import hashlib
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from dotenv import load_dotenv
from app.graph.graph import pr_pilot_graph

load_dotenv()

app = FastAPI(title="PR Pilot")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "pr-pilot-secret")


def verify_signature(payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def run_review(pr_number: int, repo: str):
    print(f"\n Starting review for PR #{pr_number} in {repo}")
    initial_state = {
        "pr_number": pr_number,
        "repo": repo,
        "diff": "",
        "changed_files": [],
        "ast_findings": [],
        "semgrep_findings": [],
        "llm_review": None,
        "confidence_score": 0.0,
        "final_comments": [],
        "should_post": False,
        "error": None,
        "run_id": f"pr-{repo}-{pr_number}"
    }
    try:
        await pr_pilot_graph.ainvoke(initial_state)
        print(f"Review complete for PR #{pr_number}")
    except Exception as e:
        print(f"Error reviewing PR #{pr_number}: {e}")


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    action = payload.get("action")

    if action in ("opened", "synchronize"):
        pr_number = payload["pull_request"]["number"]
        repo = payload["repository"]["full_name"]
        background_tasks.add_task(run_review, pr_number, repo)

    return {"status": "queued"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pr-pilot"}