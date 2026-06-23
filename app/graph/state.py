from typing import TypedDict, Optional
from pydantic import BaseModel
from typing import Literal


class ChangedFile(TypedDict):
    filename: str
    patch: str
    additions: int
    deletions: int


class ASTFinding(TypedDict):
    filename: str
    function_name: str
    signature: str
    has_docstring: bool
    complexity: int


class SemgrepFinding(TypedDict):
    filename: str
    line: int
    rule_id: str
    message: str
    severity: str


class ReviewComment(BaseModel):
    file: str
    line: int
    severity: Literal["critical", "major", "minor", "nit"]
    category: Literal["security", "correctness", "performance", "style"]
    message: str
    suggestion: str
    confidence: float


class LLMReview(BaseModel):
    intent_summary: str
    comments: list[ReviewComment]
    overall_confidence: float


class PRReviewState(TypedDict):
    # Input
    pr_number: int
    repo: str

    # Loaded data
    diff: str
    changed_files: list[ChangedFile]

    # Parallel node outputs
    ast_findings: list[ASTFinding]
    semgrep_findings: list[SemgrepFinding]
    llm_review: Optional[LLMReview]

    # Synthesized output
    confidence_score: float
    final_comments: list[ReviewComment]
    should_post: bool

    # Meta
    error: Optional[str]
    run_id: Optional[str]