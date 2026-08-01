from el_zachariahs_drivers.review_triggers import ReviewTriggerState, verify_review_trigger


def test_review_trigger_ready_when_formal_request_exists():
    result = verify_review_trigger(
        target_reviewer="el-micaiah",
        pr_url="https://github.com/el-zachariah/example/pull/1",
        repo_visibility="PRIVATE",
        reviewer_permission="read",
        review_requests=["el-micaiah"],
        latest_reviewers=[],
    )

    assert result.state == ReviewTriggerState.READY
    assert result.can_wait_for_review is True
    assert result.required_decision is None


def test_review_trigger_blocks_private_repo_without_reviewer_access():
    result = verify_review_trigger(
        target_reviewer="el-micaiah",
        pr_url="https://github.com/el-zachariah/example/pull/1",
        repo_visibility="PRIVATE",
        reviewer_permission="none",
        review_requests=[],
        latest_reviewers=[],
        tag_comment_url="https://github.com/el-zachariah/example/pull/1#issuecomment-1",
    )

    assert result.state == ReviewTriggerState.BLOCKED_REVIEWER_ACCESS
    assert result.can_wait_for_review is False
    assert result.required_decision == (
        "Grant el-micaiah repo access, change repo visibility, or choose a reviewer with access."
    )
    assert "permission becomes non-none" in result.resume_condition


def test_review_trigger_marks_comment_tag_as_weak_notification_only():
    result = verify_review_trigger(
        target_reviewer="el-micaiah",
        pr_url="https://github.com/el-zachariah/example/pull/1",
        repo_visibility="PUBLIC",
        reviewer_permission="read",
        review_requests=[],
        latest_reviewers=[],
        tag_comment_url="https://github.com/el-zachariah/example/pull/1#issuecomment-1",
    )

    assert result.state == ReviewTriggerState.WEAK_NOTIFICATION_ONLY
    assert result.can_wait_for_review is False
    assert result.required_decision == (
        "Convert tag/comment notification into a formal review request or choose a verified review route."
    )
