class AudioType(str, Enum):
    # Git
    GIT_CREATE_BRANCH = "git_create_branch"
    GIT_COMMIT = "git_commit"
    GIT_PUSH = "git_push"
    GIT_PULL = "git_pull"
    GIT_MERGE = "git_merge"
    GIT_CREATE_PR = "git_create_pr"
    GIT_CHECKOUT = "git_checkout"
    GIT_STATUS = "git_status"
    GIT_STASH = "git_stash"
    GIT_TAG = "git_tag"
