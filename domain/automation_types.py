from enum import Enum


class AutomationType(str, Enum):
    # Git
    GIT_CREATE_BRANCH    = "git_create_branch"
    GIT_COMMIT           = "git_commit"
    GIT_PUSH             = "git_push"
    GIT_PULL             = "git_pull"
    GIT_MERGE            = "git_merge"
    GIT_CREATE_PR        = "git_create_pr"
    GIT_CHECKOUT         = "git_checkout"
    GIT_STATUS           = "git_status"
    GIT_STASH            = "git_stash"
    GIT_TAG              = "git_tag"

    # GitHub (API-level)
    GITHUB_CREATE_REPO   = "github_create_repo"
    GITHUB_CREATE_ISSUE  = "github_create_issue"
    GITHUB_LIST_PRS      = "github_list_prs"

    # File & Project Scaffolding
    SCAFFOLD_PROJECT     = "scaffold_project"
    CREATE_FILE          = "create_file"
    CREATE_FOLDER        = "create_folder"
    RENAME_FILE          = "rename_file"
    DELETE_FILE          = "delete_file"
    SEARCH_IN_FILES      = "search_in_files"

    # MCP / AI
    MCP_QUERY            = "mcp_query"
    AI_SUMMARIZE         = "ai_summarize"
    AI_REVIEW_CODE       = "ai_review_code"
    AI_EXPLAIN_FILE      = "ai_explain_file"
    AI_GENERATE_TESTS    = "ai_generate_tests"
    AI_GENERATE_DOCS     = "ai_generate_docs"

    # Assistant core (your existing ones)
    GET_MODEL_CONF       = "get_model_conf"
    MANUAL_INPUT         = "manual_input"
    VOICE_INPUT          = "voice_input"


class AutomationStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCESS   = "success"
    FAILED    = "failed"
    CANCELLED = "cancelled"