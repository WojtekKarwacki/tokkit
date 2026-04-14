"""Fixtures for GitHub CLI output parser."""

# ---------------------------------------------------------------------------
# gh pr list
# ---------------------------------------------------------------------------

GH_PR_LIST = """\
Showing 5 of 12 open pull requests in owner/repo

#47\tfix: resolve auth token expiry race condition\tfeat/auth-fix\tOPEN
#45\tfeat: add dark mode support to dashboard\tfeat/dark-mode\tOPEN
#43\trefactor: extract user service layer\trefactor/user-service\tOPEN
#41\tdocs: update API reference for v2 endpoints\tdocs/api-v2\tOPEN
#38\tbuild: upgrade webpack to v5.96\tbuild/webpack-upgrade\tDRAFT
"""

# ---------------------------------------------------------------------------
# gh issue list
# ---------------------------------------------------------------------------

GH_ISSUE_LIST = """\
Showing 5 of 23 open issues in owner/repo

#102\tAuth tokens expire too early\tbug,auth\tOPEN
#98\tDark mode flickers on page load\tbug,ui\tOPEN
#95\tAdd rate limiting to public API endpoints\tenhancement,api\tOPEN
#91\tMigration script fails on PostgreSQL 15\tbug,database\tOPEN
#87\tDocument webhook payload format\tdocumentation\tOPEN
"""

# ---------------------------------------------------------------------------
# gh run list
# ---------------------------------------------------------------------------

GH_RUN_LIST = """\
STATUS\tNAME\tWORKFLOW\tBRANCH\tEVENT\tID\tELAPSED\tAGE
completed\tCI\tci.yml\tmain\tpush\t12345678\t2m34s\t2 hours ago
completed\tCI\tci.yml\tfeat/auth-fix\tpull_request\t12345677\t1m58s\t3 hours ago
failed\tCI\tci.yml\tfeat/dark-mode\tpull_request\t12345676\t3m12s\t5 hours ago
completed\tRelease\trelease.yml\tmain\tpush\t12345675\t8m45s\t1 day ago
in_progress\tCI\tci.yml\trefactor/user-service\tpull_request\t12345674\t45s\t10 minutes ago
"""
