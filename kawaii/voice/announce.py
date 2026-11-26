"""What she says when news comes in from the background watchers."""


def pr_news(new):
    """New pull-request comments -> (voice line kind, its fields): one comment, a review
    verdict, or how many came in (naming the latest)."""
    c = new[-1]
    fields = {"who": c["author"], "repo": c["repo"].split("/")[-1].replace("-", " ").replace("_", " "),
              "number": c["number"], "count": len(new)}
    if len(new) > 1:
        return "pr_comments", fields
    verdict = c.get("state") if c["kind"] == "review" else None
    return {"APPROVED": "pr_approved", "CHANGES_REQUESTED": "pr_changes"}.get(verdict, "pr_comment"), fields


def endpoint_down(went_down):
    """The name she gives the endpoints that stopped answering."""
    if len(went_down) > 1:
        return f"{len(went_down)} endpoints"
    e = went_down[0]
    return e.get("title") or e["url"].split("://", 1)[-1].split("/")[0]
