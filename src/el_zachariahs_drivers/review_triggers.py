"""Review request trigger verification helpers.

The driver should not enter REVIEW_WAIT just because it attempted to notify a
reviewer. It must verify that a durable pickup signal exists, or record a
blocker/resume condition that explains why review cannot start yet.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ReviewTriggerState(StrEnum):
    """Observed state after attempting to route a review request."""

    READY = "READY"
    WEAK_NOTIFICATION_ONLY = "WEAK_NOTIFICATION_ONLY"
    BLOCKED_REVIEWER_ACCESS = "BLOCKED_REVIEWER_ACCESS"


class ReviewTriggerVerification(BaseModel):
    """Adapter-neutral verification result for a review request attempt."""

    target_reviewer: str
    pr_url: str
    repo_visibility: str | None = None
    reviewer_permission: str | None = None
    review_requests: list[str] = Field(default_factory=list)
    latest_reviewers: list[str] = Field(default_factory=list)
    tag_comment_url: str | None = None
    state: ReviewTriggerState
    resume_condition: str
    required_decision: str | None = None

    @property
    def can_wait_for_review(self) -> bool:
        """True only when a real pickup signal exists."""

        return self.state == ReviewTriggerState.READY


def verify_review_trigger(
    *,
    target_reviewer: str,
    pr_url: str,
    repo_visibility: str | None,
    reviewer_permission: str | None,
    review_requests: list[str],
    latest_reviewers: list[str],
    tag_comment_url: str | None = None,
) -> ReviewTriggerVerification:
    """Classify whether a review request produced a durable trigger.

    A formal review request or an actual review is strong enough to enter or stay
    in REVIEW_WAIT. A plain tag/comment is weaker: useful evidence, but not a
    formal GitHub review trigger. A private repo with no reviewer permission is a
    human-authority blocker because the review cannot be assigned.
    """

    normalized_permission = (reviewer_permission or "").lower()
    has_access = normalized_permission not in {"", "none"}
    reviewer_requested = target_reviewer in review_requests
    reviewer_started = target_reviewer in latest_reviewers

    if reviewer_requested or reviewer_started:
        return ReviewTriggerVerification(
            target_reviewer=target_reviewer,
            pr_url=pr_url,
            repo_visibility=repo_visibility,
            reviewer_permission=reviewer_permission,
            review_requests=review_requests,
            latest_reviewers=latest_reviewers,
            tag_comment_url=tag_comment_url,
            state=ReviewTriggerState.READY,
            resume_condition=(
                f"reviewRequests includes {target_reviewer} or latestReviews contains {target_reviewer}"
            ),
        )

    if (repo_visibility or "").upper() == "PRIVATE" and not has_access:
        return ReviewTriggerVerification(
            target_reviewer=target_reviewer,
            pr_url=pr_url,
            repo_visibility=repo_visibility,
            reviewer_permission=reviewer_permission,
            review_requests=review_requests,
            latest_reviewers=latest_reviewers,
            tag_comment_url=tag_comment_url,
            state=ReviewTriggerState.BLOCKED_REVIEWER_ACCESS,
            resume_condition=(
                f"{target_reviewer} permission becomes non-none, repo visibility changes, "
                f"or another accessible reviewer is selected"
            ),
            required_decision=(
                f"Grant {target_reviewer} repo access, change repo visibility, "
                f"or choose a reviewer with access."
            ),
        )

    return ReviewTriggerVerification(
        target_reviewer=target_reviewer,
        pr_url=pr_url,
        repo_visibility=repo_visibility,
        reviewer_permission=reviewer_permission,
        review_requests=review_requests,
        latest_reviewers=latest_reviewers,
        tag_comment_url=tag_comment_url,
        state=ReviewTriggerState.WEAK_NOTIFICATION_ONLY,
        resume_condition=(
            f"formal review request for {target_reviewer}, latest review by {target_reviewer}, "
            "or explicit process-steward reviewer reroute"
        ),
        required_decision=(
            "Convert tag/comment notification into a formal review request or choose a verified review route."
        ),
    )
