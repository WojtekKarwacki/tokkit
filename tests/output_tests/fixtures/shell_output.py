"""Fixtures for shell tool output parsers: package lists, file listings, search, and env."""

# ---------------------------------------------------------------------------
# pip list
# ---------------------------------------------------------------------------

PIP_LIST = """\
Package                   Version
------------------------- ---------
annotated-types           0.7.0
anyio                     4.7.0
attrs                     24.2.0
black                     24.10.0
boto3                     1.35.76
botocore                  1.35.76
certifi                   2024.11.26
charset-normalizer        3.4.0
click                     8.1.8
colorama                  0.4.6
cryptography              44.0.0
decorator                 5.1.1
filelock                  3.16.1
flask                     3.1.0
httpx                     0.27.2
idna                      3.10
importlib-metadata        8.5.0
jinja2                    3.1.4
jsonschema                4.23.0
markupsafe                3.0.2
mypy                      1.13.0
numpy                     2.1.3
packaging                 24.2
paramiko                  3.5.0
pillow                    11.0.0
pip                       24.3.1
platformdirs              4.3.6
psycopg2-binary           2.9.10
pydantic                  2.10.3
pytest                    8.3.4
"""

# ---------------------------------------------------------------------------
# pip freeze
# ---------------------------------------------------------------------------

PIP_FREEZE = """\
annotated-types==0.7.0
anyio==4.7.0
attrs==24.2.0
black==24.10.0
boto3==1.35.76
botocore==1.35.76
certifi==2024.11.26
charset-normalizer==3.4.0
click==8.1.8
colorama==0.4.6
cryptography==44.0.0
decorator==5.1.1
filelock==3.16.1
flask==3.1.0
httpx==0.27.2
idna==3.10
importlib-metadata==8.5.0
jinja2==3.1.4
jsonschema==4.23.0
markupsafe==3.0.2
mypy==1.13.0
numpy==2.1.3
packaging==24.2
paramiko==3.5.0
pillow==11.0.0
pip==24.3.1
platformdirs==4.3.6
psycopg2-binary==2.9.10
pydantic==2.10.3
pytest==8.3.4
"""

# ---------------------------------------------------------------------------
# npm ls
# ---------------------------------------------------------------------------

NPM_LS = """\
my-app@1.0.0 /home/user/my-app
├── express@4.18.2
│   ├── accepts@1.3.8
│   │   ├── mime-types@2.1.35
│   │   └── negotiator@0.6.3
│   ├── array-flatten@1.1.1
│   ├── body-parser@1.20.2
│   │   ├── bytes@3.1.2
│   │   └── content-type@1.0.5
│   ├── content-disposition@0.5.4
│   ├── cookie@0.5.0
│   ├── debug@2.6.9
│   └── path-to-regexp@0.1.7
├── lodash@4.17.21
├── axios@1.7.7
│   ├── follow-redirects@1.15.9
│   ├── form-data@4.0.1
│   └── proxy-from-env@1.1.0
├── react@18.3.1
│   └── loose-envify@1.4.0
├── typescript@5.6.3
├── jest@29.7.0
│   ├── @jest/core@29.7.0
│   │   ├── @jest/reporters@29.7.0
│   │   └── @jest/test-sequencer@29.7.0
│   ├── @jest/globals@29.7.0
│   └── jest-circus@29.7.0
├── UNMET PEER DEPENDENCY react-dom@18.3.1
└── webpack@5.96.1
    ├── @webpack-cli/configtest@2.1.1
    ├── acorn@8.14.0
    ├── browserslist@4.24.2
    └── watchpack@2.4.2
"""

# ---------------------------------------------------------------------------
# tree
# ---------------------------------------------------------------------------

TREE_OUTPUT = """\
.
├── README.md
├── package.json
├── src
│   ├── components
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   ├── Form.tsx
│   │   └── Modal.tsx
│   ├── hooks
│   │   ├── useAuth.ts
│   │   ├── useForm.ts
│   │   └── useQuery.ts
│   ├── pages
│   │   ├── dashboard
│   │   │   ├── index.tsx
│   │   │   ├── Analytics.tsx
│   │   │   └── Settings.tsx
│   │   ├── auth
│   │   │   ├── login.tsx
│   │   │   └── register.tsx
│   │   └── index.tsx
│   ├── utils
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   └── format.ts
│   └── index.ts
├── tests
│   ├── unit
│   │   ├── Button.test.tsx
│   │   └── Form.test.tsx
│   └── integration
│       └── auth.test.ts
└── tsconfig.json

9 directories, 22 files
"""

# ---------------------------------------------------------------------------
# ls -la
# ---------------------------------------------------------------------------

LS_LA_OUTPUT = """\
total 248
drwxr-xr-x  3 user group  4096 Nov 20 10:15 .
drwxr-xr-x 12 user group  4096 Nov 20 10:00 ..
-rw-r--r--  1 user group   220 Nov 20 10:00 .bash_logout
-rw-r--r--  1 user group  3526 Nov 20 10:00 .bashrc
drwxr-xr-x  3 user group  4096 Nov 20 10:15 .config
-rw-r--r--  1 user group   807 Nov 20 10:00 .profile
-rw-r--r--  1 user group  1234 Nov 20 10:10 README.md
-rw-r--r--  1 user group  2048 Nov 20 10:10 Makefile
-rw-r--r--  1 user group   512 Nov 20 10:10 .env.example
-rw-r--r--  1 user group   102 Nov 20 10:10 .gitignore
-rw-r--r--  1 user group  4096 Nov 20 10:10 package.json
-rw-r--r--  1 user group 98304 Nov 20 10:10 package-lock.json
-rw-r--r--  1 user group  1024 Nov 20 10:10 tsconfig.json
-rw-r--r--  1 user group   512 Nov 20 10:10 jest.config.js
-rw-r--r--  1 user group   256 Nov 20 10:10 .eslintrc.js
-rw-r--r--  1 user group   512 Nov 20 10:10 babel.config.js
-rw-r--r--  1 user group  2048 Nov 20 10:10 webpack.config.js
-rw-r--r--  1 user group  1024 Nov 20 10:10 rollup.config.js
-rw-r--r--  1 user group   512 Nov 20 10:10 vite.config.ts
-rw-r--r--  1 user group   768 Nov 20 10:10 vitest.config.ts
-rwxr-xr-x  1 user group   128 Nov 20 10:10 start.sh
-rwxr-xr-x  1 user group   256 Nov 20 10:10 deploy.sh
-rwxr-xr-x  1 user group   192 Nov 20 10:10 build.sh
-rw-r--r--  1 user group  3072 Nov 20 10:10 CHANGELOG.md
-rw-r--r--  1 user group  1536 Nov 20 10:10 CONTRIBUTING.md
-rw-r--r--  1 user group   896 Nov 20 10:10 LICENSE
-rw-r--r--  1 user group  2560 Nov 20 10:10 pyproject.toml
-rw-r--r--  1 user group  1792 Nov 20 10:10 setup.cfg
-rw-r--r--  1 user group   384 Nov 20 10:10 setup.py
-rw-r--r--  1 user group 45056 Nov 20 10:10 uv.lock
-rw-r--r--  1 user group  1024 Nov 20 10:10 requirements.txt
-rw-r--r--  1 user group   640 Nov 20 10:10 requirements-dev.txt
-rw-r--r--  1 user group  8192 Nov 20 10:10 Cargo.toml
-rw-r--r--  1 user group 32768 Nov 20 10:10 Cargo.lock
-rw-r--r--  1 user group   128 Nov 20 10:10 rust-toolchain.toml
-rw-r--r--  1 user group   256 Nov 20 10:10 clippy.toml
-rw-r--r--  1 user group   512 Nov 20 10:10 .cargo
-rw-r--r--  1 user group   768 Nov 20 10:10 .github
-rw-r--r--  1 user group  1024 Nov 20 10:10 docker-compose.yml
-rw-r--r--  1 user group   512 Nov 20 10:10 Dockerfile
-rw-r--r--  1 user group   384 Nov 20 10:10 .dockerignore
-rw-r--r--  1 user group  4096 Nov 20 10:10 docs
-rw-r--r--  1 user group  2048 Nov 20 10:10 scripts
-rw-r--r--  1 user group   512 Nov 20 10:10 infra
-rw-r--r--  1 user group  1024 Nov 20 10:10 config
-rw-r--r--  1 user group   256 Nov 20 10:10 migrations
-rw-r--r--  1 user group   128 Nov 20 10:10 fixtures
-rw-r--r--  1 user group   512 Nov 20 10:10 examples
-rw-r--r--  1 user group  2048 Nov 20 10:10 benchmarks
-rw-r--r--  1 user group  1024 Nov 20 10:10 notebooks
-rw-r--r--  1 user group   512 Nov 20 10:10 assets
-rw-r--r--  1 user group   256 Nov 20 10:10 static
-rw-r--r--  1 user group   128 Nov 20 10:10 public
-rw-r--r--  1 user group   512 Nov 20 10:10 templates
-rw-r--r--  1 user group   256 Nov 20 10:10 locale
-rw-r--r--  1 user group   512 Nov 20 10:10 i18n
-rw-r--r--  1 user group   128 Nov 20 10:10 data
-rw-r--r--  1 user group   256 Nov 20 10:10 cache
-rw-r--r--  1 user group   512 Nov 20 10:10 logs
-rw-r--r--  1 user group   128 Nov 20 10:10 tmp
"""

# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------

FIND_OUTPUT = """\
./src/auth.py
./src/db.py
./src/main.py
./src/models.py
./src/utils.py
./src/config.py
./src/routes/users.py
./src/routes/auth.py
./src/routes/posts.py
./src/services/user_service.py
./src/services/auth_service.py
./src/services/email_service.py
./src/services/notification_service.py
./tests/test_auth.py
./tests/test_db.py
./tests/test_models.py
./tests/test_utils.py
./tests/test_routes.py
./tests/fixtures/users.py
./tests/fixtures/posts.py
./tests/integration/test_api.py
./tests/integration/test_auth_flow.py
./tests/integration/test_db_migrations.py
./scripts/migrate.py
./scripts/seed.py
./scripts/cleanup.py
./scripts/backup.py
./scripts/restore.py
./docs/api.md
./docs/setup.md
./docs/deployment.md
./docs/contributing.md
./docs/architecture.md
./config/settings.py
./config/logging.py
./config/database.py
./config/celery.py
./migrations/0001_initial.py
./migrations/0002_add_users.py
./migrations/0003_add_posts.py
./migrations/0004_add_indexes.py
./migrations/0005_add_foreign_keys.py
./benchmarks/bench_auth.py
./benchmarks/bench_db.py
./benchmarks/bench_api.py
./examples/basic_usage.py
./examples/advanced_usage.py
./examples/webhook_example.py
"""

# ---------------------------------------------------------------------------
# grep results
# ---------------------------------------------------------------------------

GREP_RESULTS = """\
src/auth.py:12:def authenticate(user, password):
src/auth.py:45:    if not authenticate(username, raw_password):
src/auth.py:67:    token = authenticate_with_token(request.headers.get('Authorization'))
src/auth.py:89:def authenticate_with_token(token):
src/auth.py:102:    result = authenticate(user.username, provided_password)
src/auth.py:115:    cached = _auth_cache.get(authenticate.__name__)
src/auth.py:130:# authenticate is the main entry point
src/auth.py:145:    return authenticate(username, password)
src/auth.py:167:    return not authenticate(user, "")
src/auth.py:182:    raise AuthError("authenticate failed")
src/middleware.py:8:from src.auth import authenticate
src/middleware.py:23:    user = authenticate(request.user, request.password)
src/middleware.py:41:    if not authenticate(token=bearer_token):
src/middleware.py:58:    logger.debug("authenticate called")
src/tests/test_auth.py:5:from src.auth import authenticate
src/tests/test_auth.py:18:    result = authenticate("admin", "correct_password")
src/tests/test_auth.py:25:    result = authenticate("admin", "wrong_password")
src/tests/test_auth.py:32:    result = authenticate("", "")
src/tests/test_auth.py:39:    with pytest.raises(AuthError):
src/tests/test_auth.py:46:        authenticate(None, None)
src/api/endpoints.py:14:from src.auth import authenticate
src/api/endpoints.py:67:    user = authenticate(payload["username"], payload["password"])
src/api/endpoints.py:89:    if authenticate(token=request.headers["X-Auth-Token"]):
src/config/security.py:3:# Authentication configuration
src/config/security.py:19:AUTH_BACKEND = "src.auth.authenticate"
Binary file src/compiled/auth.pyc matches
src/utils/helpers.py:7:def wrap_authenticate(fn):
src/utils/helpers.py:22:    return wrap_authenticate
"""

# ---------------------------------------------------------------------------
# env output
# ---------------------------------------------------------------------------

ENV_OUTPUT = """\
HOME=/home/user
SHELL=/bin/bash
USER=user
LANG=en_US.UTF-8
PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin
TERM=xterm-256color
EDITOR=vim
VISUAL=vim
PAGER=less
LESS=-R
COLORTERM=truecolor
DISPLAY=:0
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
XDG_RUNTIME_DIR=/run/user/1000
XDG_SESSION_TYPE=x11
VIRTUAL_ENV=/home/user/project/.venv
PYTHONPATH=/home/user/project/src
DATABASE_URL=postgresql://localhost:5432/mydb
REDIS_URL=redis://localhost:6379/0
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
SECRET_KEY=super-secret-django-key-do-not-share
API_TOKEN=tok_live_xxxxxxxxxxxxxxxxxxxxxxxxxxx
DATABASE_PASSWORD=mydbpassword123
JWT_SECRET=my-jwt-signing-secret-key
STRIPE_SECRET_KEY=sk_test_fake_fixture_value_000
"""
