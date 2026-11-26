from kawaii.voice.announce import endpoint_down, pr_news


def comment(**kw):
    return {"author": "ana", "repo": "me/my-cool_app", "number": 7, "kind": "comment", **kw}


def test_one_comment():
    assert pr_news([comment()]) == ("pr_comment", {"who": "ana", "repo": "my cool app", "number": 7, "count": 1})


def test_review_verdicts():
    assert pr_news([comment(kind="review", state="APPROVED")])[0] == "pr_approved"
    assert pr_news([comment(kind="review", state="CHANGES_REQUESTED")])[0] == "pr_changes"
    assert pr_news([comment(kind="review", state="COMMENTED")])[0] == "pr_comment"


def test_several_comments_are_counted_and_name_the_latest():
    kind, fields = pr_news([comment(author="bo"), comment(author="cy")])
    assert kind == "pr_comments" and fields["count"] == 2 and fields["who"] == "cy"


def test_endpoint_down_names_it_or_counts_them():
    assert endpoint_down([{"url": "https://api.x.dev/health", "title": ""}]) == "api.x.dev"
    assert endpoint_down([{"url": "https://a.dev", "title": "Billing"}]) == "Billing"
    assert endpoint_down([{"url": "https://a.dev"}, {"url": "https://b.dev"}]) == "2 endpoints"
