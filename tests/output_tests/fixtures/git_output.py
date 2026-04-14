"""Realistic git command output fixtures for diff, status, log, show, blame, branch, and stash."""

# ---------------------------------------------------------------------------
# Diff fixtures
# ---------------------------------------------------------------------------

DIFF_SIMPLE = """\
diff --git a/src/auth.py b/src/auth.py
index 3b4a1c2..7f9e0d1 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -12,10 +12,13 @@ import hashlib
 class AuthService:
     def __init__(self, secret: str):
         self.secret = secret
+        self.token_ttl = 3600

     def generate_token(self, user_id: str) -> str:
-        payload = {"user_id": user_id}
+        payload = {"user_id": user_id, "exp": time.time() + self.token_ttl}
         return jwt.encode(payload, self.secret, algorithm="HS256")

+    def revoke_token(self, token: str) -> None:
+        self._revoked.add(token)
+
 @@ -45,7 +48,7 @@ class AuthService:

     def validate(self, token: str) -> bool:
-        return token not in self._expired
+        return token not in self._revoked
"""

DIFF_WITH_LOCKFILE = """\
diff --git a/src/utils.py b/src/utils.py
index a1b2c3d..e4f5678 100644
--- a/src/utils.py
+++ b/src/utils.py
@@ -5,6 +5,7 @@ import os
 import sys

 def get_env(key: str, default: str = "") -> str:
+    # Retrieve an environment variable with a fallback.
     return os.environ.get(key, default)

diff --git a/package-lock.json b/package-lock.json
index 000aaaa..111bbbb 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,5 +1,5 @@
 {
-  "lockfileVersion": 2,
+  "lockfileVersion": 3,
   "name": "my-app",
   "version": "1.0.0",
   "packages": {
@@ -10,7 +10,7 @@
       "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.20.tgz",
       "integrity": "sha512-fake=="
     },
-    "node_modules/lodash": {
+    "node_modules/lodash-es": {
       "version": "4.17.21",
       "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.21.tgz",
       "integrity": "sha512-real=="
@@ -20,5 +20,105 @@
+    "node_modules/pkg-01": { "version": "1.0.0" },
+    "node_modules/pkg-02": { "version": "1.0.0" },
+    "node_modules/pkg-03": { "version": "1.0.0" },
+    "node_modules/pkg-04": { "version": "1.0.0" },
+    "node_modules/pkg-05": { "version": "1.0.0" },
+    "node_modules/pkg-06": { "version": "1.0.0" },
+    "node_modules/pkg-07": { "version": "1.0.0" },
+    "node_modules/pkg-08": { "version": "1.0.0" },
+    "node_modules/pkg-09": { "version": "1.0.0" },
+    "node_modules/pkg-10": { "version": "1.0.0" },
+    "node_modules/pkg-11": { "version": "1.0.0" },
+    "node_modules/pkg-12": { "version": "1.0.0" },
+    "node_modules/pkg-13": { "version": "1.0.0" },
+    "node_modules/pkg-14": { "version": "1.0.0" },
+    "node_modules/pkg-15": { "version": "1.0.0" },
+    "node_modules/pkg-16": { "version": "1.0.0" },
+    "node_modules/pkg-17": { "version": "1.0.0" },
+    "node_modules/pkg-18": { "version": "1.0.0" },
+    "node_modules/pkg-19": { "version": "1.0.0" },
+    "node_modules/pkg-20": { "version": "1.0.0" },
+    "node_modules/pkg-21": { "version": "1.0.0" },
+    "node_modules/pkg-22": { "version": "1.0.0" },
+    "node_modules/pkg-23": { "version": "1.0.0" },
+    "node_modules/pkg-24": { "version": "1.0.0" },
+    "node_modules/pkg-25": { "version": "1.0.0" },
+    "node_modules/pkg-26": { "version": "1.0.0" },
+    "node_modules/pkg-27": { "version": "1.0.0" },
+    "node_modules/pkg-28": { "version": "1.0.0" },
+    "node_modules/pkg-29": { "version": "1.0.0" },
+    "node_modules/pkg-30": { "version": "1.0.0" },
+    "node_modules/pkg-31": { "version": "1.0.0" },
+    "node_modules/pkg-32": { "version": "1.0.0" },
+    "node_modules/pkg-33": { "version": "1.0.0" },
+    "node_modules/pkg-34": { "version": "1.0.0" },
+    "node_modules/pkg-35": { "version": "1.0.0" },
+    "node_modules/pkg-36": { "version": "1.0.0" },
+    "node_modules/pkg-37": { "version": "1.0.0" },
+    "node_modules/pkg-38": { "version": "1.0.0" },
+    "node_modules/pkg-39": { "version": "1.0.0" },
+    "node_modules/pkg-40": { "version": "1.0.0" },
+    "node_modules/pkg-41": { "version": "1.0.0" },
+    "node_modules/pkg-42": { "version": "1.0.0" },
+    "node_modules/pkg-43": { "version": "1.0.0" },
+    "node_modules/pkg-44": { "version": "1.0.0" },
+    "node_modules/pkg-45": { "version": "1.0.0" },
+    "node_modules/pkg-46": { "version": "1.0.0" },
+    "node_modules/pkg-47": { "version": "1.0.0" },
+    "node_modules/pkg-48": { "version": "1.0.0" },
+    "node_modules/pkg-49": { "version": "1.0.0" },
+    "node_modules/pkg-50": { "version": "1.0.0" },
+    "node_modules/pkg-51": { "version": "1.0.0" },
+    "node_modules/pkg-52": { "version": "1.0.0" },
+    "node_modules/pkg-53": { "version": "1.0.0" },
+    "node_modules/pkg-54": { "version": "1.0.0" },
+    "node_modules/pkg-55": { "version": "1.0.0" },
+    "node_modules/pkg-56": { "version": "1.0.0" },
+    "node_modules/pkg-57": { "version": "1.0.0" },
+    "node_modules/pkg-58": { "version": "1.0.0" },
+    "node_modules/pkg-59": { "version": "1.0.0" },
+    "node_modules/pkg-60": { "version": "1.0.0" },
+    "node_modules/pkg-61": { "version": "1.0.0" },
+    "node_modules/pkg-62": { "version": "1.0.0" },
+    "node_modules/pkg-63": { "version": "1.0.0" },
+    "node_modules/pkg-64": { "version": "1.0.0" },
+    "node_modules/pkg-65": { "version": "1.0.0" },
+    "node_modules/pkg-66": { "version": "1.0.0" },
+    "node_modules/pkg-67": { "version": "1.0.0" },
+    "node_modules/pkg-68": { "version": "1.0.0" },
+    "node_modules/pkg-69": { "version": "1.0.0" },
+    "node_modules/pkg-70": { "version": "1.0.0" },
+    "node_modules/pkg-71": { "version": "1.0.0" },
+    "node_modules/pkg-72": { "version": "1.0.0" },
+    "node_modules/pkg-73": { "version": "1.0.0" },
+    "node_modules/pkg-74": { "version": "1.0.0" },
+    "node_modules/pkg-75": { "version": "1.0.0" },
+    "node_modules/pkg-76": { "version": "1.0.0" },
+    "node_modules/pkg-77": { "version": "1.0.0" },
+    "node_modules/pkg-78": { "version": "1.0.0" },
+    "node_modules/pkg-79": { "version": "1.0.0" },
+    "node_modules/pkg-80": { "version": "1.0.0" },
+    "node_modules/pkg-81": { "version": "1.0.0" },
+    "node_modules/pkg-82": { "version": "1.0.0" },
+    "node_modules/pkg-83": { "version": "1.0.0" },
+    "node_modules/pkg-84": { "version": "1.0.0" },
+    "node_modules/pkg-85": { "version": "1.0.0" },
+    "node_modules/pkg-86": { "version": "1.0.0" },
+    "node_modules/pkg-87": { "version": "1.0.0" },
+    "node_modules/pkg-88": { "version": "1.0.0" },
+    "node_modules/pkg-89": { "version": "1.0.0" },
+    "node_modules/pkg-90": { "version": "1.0.0" },
+    "node_modules/pkg-91": { "version": "1.0.0" },
+    "node_modules/pkg-92": { "version": "1.0.0" },
+    "node_modules/pkg-93": { "version": "1.0.0" },
+    "node_modules/pkg-94": { "version": "1.0.0" },
+    "node_modules/pkg-95": { "version": "1.0.0" },
+    "node_modules/pkg-96": { "version": "1.0.0" },
+    "node_modules/pkg-97": { "version": "1.0.0" },
+    "node_modules/pkg-98": { "version": "1.0.0" },
+    "node_modules/pkg-99": { "version": "1.0.0" },
+    "node_modules/pkg-100": { "version": "1.0.0" }
   }
 }
"""

DIFF_LARGE_HUNK = """\
diff --git a/src/data_pipeline.py b/src/data_pipeline.py
index aabbcc1..ddeeff2 100644
--- a/src/data_pipeline.py
+++ b/src/data_pipeline.py
@@ -100,5 +100,65 @@ class DataPipeline:

     def process(self):
         results = []
+        added line 1
+        added line 2
+        added line 3
+        added line 4
+        added line 5
+        added line 6
+        added line 7
+        added line 8
+        added line 9
+        added line 10
+        added line 11
+        added line 12
+        added line 13
+        added line 14
+        added line 15
+        added line 16
+        added line 17
+        added line 18
+        added line 19
+        added line 20
+        added line 21
+        added line 22
+        added line 23
+        added line 24
+        added line 25
+        added line 26
+        added line 27
+        added line 28
+        added line 29
+        added line 30
+        added line 31
+        added line 32
+        added line 33
+        added line 34
+        added line 35
+        added line 36
+        added line 37
+        added line 38
+        added line 39
+        added line 40
+        added line 41
+        added line 42
+        added line 43
+        added line 44
+        added line 45
+        added line 46
+        added line 47
+        added line 48
+        added line 49
+        added line 50
+        added line 51
+        added line 52
+        added line 53
+        added line 54
+        added line 55
+        added line 56
+        added line 57
+        added line 58
+        added line 59
+        added line 60
         return results
"""

DIFF_STAT = """\
 src/auth.py          | 18 ++++++++++++------
 src/models/user.py   |  7 +++++--
 tests/test_auth.py   | 24 ++++++++++++++++++------
 docs/architecture.md |  3 +++
 4 files changed, 38 insertions(+), 14 deletions(-)
"""

DIFF_MULTIPLE_FILES = """\
diff --git a/src/models/user.py b/src/models/user.py
index 112233a..445566b 100644
--- a/src/models/user.py
+++ b/src/models/user.py
@@ -8,7 +8,8 @@ class User:
     id: int
     name: str
     email: str
+    created_at: datetime

     def is_active(self) -> bool:
-        return self.status == "active"
+        return self.status in ("active", "pending")

diff --git a/src/repositories/user_repo.py b/src/repositories/user_repo.py
index aabbccd..eeff001 100644
--- a/src/repositories/user_repo.py
+++ b/src/repositories/user_repo.py
@@ -22,6 +22,11 @@ class UserRepository:
     def find_by_email(self, email: str) -> Optional[User]:
         return self.db.query(User).filter(User.email == email).first()

+    def find_active(self) -> list[User]:
+        return (
+            self.db.query(User)
+            .filter(User.status.in_(["active", "pending"]))
+            .all()
+        )
+
     def delete(self, user_id: int) -> None:
         user = self.find_by_id(user_id)
         if user:
"""

# ---------------------------------------------------------------------------
# Status fixtures
# ---------------------------------------------------------------------------

STATUS_CLEAN = """\
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
"""

STATUS_DIRTY = """\
On branch feat/auth-improvements
Your branch is ahead of 'origin/feat/auth-improvements' by 2 commits.
  (use "git push" to publish your local commits)

Changes to be committed:
  (use "git restore --staged <file>..." to unstage)
	modified:   src/auth.py
	new file:   src/auth_helpers.py

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   src/models/user.py
	modified:   tests/test_auth.py
	modified:   README.md

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	.env.local
	scratch/notes.txt
"""

STATUS_SHORT = """\
M  src/auth.py
A  src/auth_helpers.py
 M src/models/user.py
 M tests/test_auth.py
 M README.md
?? .env.local
?? scratch/notes.txt
"""

STATUS_LARGE = """\
On branch feat/big-refactor
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
	modified:   src/api/routes/auth.py
	modified:   src/api/routes/users.py
	modified:   src/api/routes/items.py
	modified:   src/api/routes/orders.py
	modified:   src/api/routes/payments.py
	modified:   src/services/auth_service.py
	modified:   src/services/user_service.py
	modified:   src/services/item_service.py
	modified:   src/services/order_service.py
	modified:   src/services/payment_service.py
	modified:   src/models/user.py
	modified:   src/models/item.py
	modified:   src/models/order.py
	modified:   src/models/payment.py
	modified:   src/models/base.py
	modified:   src/repositories/user_repo.py
	modified:   src/repositories/item_repo.py
	modified:   src/repositories/order_repo.py
	modified:   src/repositories/payment_repo.py
	modified:   src/repositories/base_repo.py
	modified:   tests/test_auth.py
	modified:   tests/test_users.py
	modified:   tests/test_items.py
	modified:   tests/test_orders.py
	modified:   tests/test_payments.py
	modified:   docs/api.md
	modified:   docs/architecture.md
	modified:   docs/deployment.md
	modified:   config/settings.py
	modified:   config/logging.py

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	scratch/analysis.py
	scratch/migration_notes.md
	scratch/perf_test.py
	tmp/debug_output.txt
	tmp/profile_results.txt
	tmp/heap_dump.bin
	experiments/cache_strategy.py
	experiments/batch_processor.py
	experiments/async_pipeline.py
	experiments/connection_pool.py
	experiments/retry_logic.py
	experiments/circuit_breaker.py
	experiments/rate_limiter.py
	experiments/feature_flags.py
	experiments/ab_testing.py
"""

# ---------------------------------------------------------------------------
# Log fixtures
# ---------------------------------------------------------------------------

LOG_VERBOSE = """\
commit a1b2c3d4e5f6789012345678901234567890abcd
Author: Alice Johnson <alice@example.com>
Date:   Mon Apr 7 14:32:10 2025 +0000

    feat: add token refresh endpoint

    Adds POST /auth/refresh that accepts a valid JWT and returns a new
    short-lived access token plus an updated refresh token. Includes
    rate limiting to prevent abuse.

commit b2c3d4e5f6789012345678901234567890abcde1
Author: Bob Smith <bob@example.com>
Date:   Sun Apr 6 11:15:42 2025 +0000

    fix: handle expired tokens in middleware

    The JWT middleware was silently passing expired tokens through to
    route handlers. Now returns 401 with a clear error message.

commit c3d4e5f6789012345678901234567890abcdef12
Author: Alice Johnson <alice@example.com>
Date:   Fri Apr 4 09:00:00 2025 +0000

    chore: update dependencies

    Bumps jwt to 2.8.0, cryptography to 42.0.5. No breaking changes.
"""

LOG_ONELINE = """\
a1b2c3d feat: add token refresh endpoint
b2c3d4e fix: handle expired tokens in middleware
c3d4e5f chore: update dependencies
d4e5f6a test: add coverage for auth edge cases
e5f6a7b refactor: extract token validation to service
f6a7b8c docs: update API documentation for auth endpoints
a7b8c9d feat: add rate limiting to login endpoint
b8c9d0e fix: correct CORS headers for preflight requests
c9d0e1f style: apply black formatting to auth module
d0e1f2a feat: add OAuth2 provider support
e1f2a3b chore: configure CI pipeline for multi-Python testing
f2a3b4c build: switch from pip to uv for dependency management
"""

LOG_ONELINE_SHORT = """\
a1b2c3d feat: add token refresh endpoint
b2c3d4e fix: handle expired tokens in middleware
c3d4e5f chore: update dependencies
"""

SHOW_COMMIT = """\
commit a1b2c3d4e5f6789012345678901234567890abcd
Author: Alice Johnson <alice@example.com>
Date:   Mon Apr 7 14:32:10 2025 +0000

    feat: add token refresh endpoint

    Adds POST /auth/refresh that accepts a valid JWT and returns a new
    short-lived access token plus an updated refresh token.

diff --git a/src/auth.py b/src/auth.py
index 3b4a1c2..7f9e0d1 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -45,6 +45,18 @@ class AuthService:
     def validate(self, token: str) -> bool:
         return token not in self._revoked

+    def refresh(self, token: str) -> tuple[str, str]:
+        if not self.validate(token):
+            raise ValueError("Token is invalid or revoked")
+        claims = jwt.decode(token, self.secret, algorithms=["HS256"])
+        user_id = claims["user_id"]
+        self.revoke_token(token)
+        access = self.generate_token(user_id)
+        refresh = self.generate_refresh_token(user_id)
+        return access, refresh
+
diff --git a/src/routes/auth.py b/src/routes/auth.py
index 9988776..aabb123 100644
--- a/src/routes/auth.py
+++ b/src/routes/auth.py
@@ -30,3 +30,12 @@ router = APIRouter()
 async def login(credentials: LoginRequest) -> TokenResponse:
     return await auth_service.login(credentials)

+
+@router.post("/refresh")
+async def refresh_token(body: RefreshRequest) -> TokenResponse:
+    access, refresh = auth_service.refresh(body.refresh_token)
+    return TokenResponse(access_token=access, refresh_token=refresh)
"""

# ---------------------------------------------------------------------------
# Blame fixture
# ---------------------------------------------------------------------------

BLAME_OUTPUT = """\
^a1b2c3d (Alice Johnson  2025-03-01 10:00:00 +0000  1) import jwt
^a1b2c3d (Alice Johnson  2025-03-01 10:00:00 +0000  2) import time
b2c3d4e5 (Bob Smith      2025-03-15 14:22:11 +0000  3) from typing import Optional
b2c3d4e5 (Bob Smith      2025-03-15 14:22:11 +0000  4)
c3d4e5f6 (Carol White    2025-03-20 09:15:33 +0000  5) class AuthService:
c3d4e5f6 (Carol White    2025-03-20 09:15:33 +0000  6)     def __init__(self, secret: str):
^a1b2c3d (Alice Johnson  2025-03-01 10:00:00 +0000  7)         self.secret = secret
b2c3d4e5 (Bob Smith      2025-03-15 14:22:11 +0000  8)         self.token_ttl = 3600
c3d4e5f6 (Carol White    2025-03-20 09:15:33 +0000  9)         self._revoked: set = set()
^a1b2c3d (Alice Johnson  2025-03-01 10:00:00 +0000 10)
b2c3d4e5 (Bob Smith      2025-03-15 14:22:11 +0000 11)     def generate_token(self, user_id: str) -> str:
c3d4e5f6 (Carol White    2025-03-20 09:15:33 +0000 12)         payload = {"user_id": user_id, "exp": time.time() + self.token_ttl}
"""

# ---------------------------------------------------------------------------
# Branch fixtures
# ---------------------------------------------------------------------------

BRANCH_OUTPUT = """\
  feat/auth-improvements
  feat/dual-model-compression
  feat/rate-limiting
  fix/cors-headers
  fix/token-expiry
  hotfix/security-patch
* main
  release/v2.0
"""

BRANCH_VERBOSE = """\
  feat/auth-improvements      a1b2c3d [origin/feat/auth-improvements] feat: add token refresh endpoint
  feat/dual-model-compression b2c3d4e feat: implement dual model pipeline
  feat/rate-limiting          c3d4e5f feat: add rate limiting to login endpoint
  fix/cors-headers            d4e5f6a fix: correct CORS headers for preflight requests
  fix/token-expiry            e5f6a7b fix: handle expired tokens in middleware
  hotfix/security-patch       f6a7b8c fix: patch JWT algorithm confusion vulnerability
* main                        a7b8c9d [origin/main] chore: release v1.9.2
  release/v2.0                b8c9d0e [origin/release/v2.0: ahead 3] build: prepare v2.0 release
"""

# ---------------------------------------------------------------------------
# Stash fixture
# ---------------------------------------------------------------------------

STASH_LIST = """\
stash@{0}: WIP on feat/auth-improvements: a1b2c3d feat: add token refresh endpoint
stash@{1}: On main: fix cors before switching branches
stash@{2}: WIP on feat/rate-limiting: c3d4e5f feat: add rate limiting to login endpoint
"""
