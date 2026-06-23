import os
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28"
}


def get_pr_diff(repo: str, pr_number: int) -> str:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {**HEADERS, "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def get_pr_files(repo: str, pr_number: int) -> list[dict]:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def post_review_comment(repo: str, pr_number: int, body: str) -> dict:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    payload = {
        "body": body,
        "event": "COMMENT"
    }
    response = requests.post(url, json=payload, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def set_commit_status(
    repo: str,
    sha: str,
    state: str,
    description: str
) -> dict:
    url = f"https://api.github.com/repos/{repo}/statuses/{sha}"
    payload = {
        "state": state,
        "description": description,
        "context": "pr-pilot/review"
    }
    response = requests.post(url, json=payload, headers=HEADERS)
    response.raise_for_status()
    return response.json()