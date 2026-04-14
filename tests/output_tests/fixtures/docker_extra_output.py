"""Realistic docker compose/ps/images/logs output fixtures."""

# ---------------------------------------------------------------------------
# docker compose ps — 5 healthy services
# ---------------------------------------------------------------------------

COMPOSE_PS = """\
NAME                    IMAGE                   COMMAND                  SERVICE    CREATED         STATUS                   PORTS
myapp-web-1             myapp-web:latest        "/docker-entrypoint.…"   web        2 hours ago     Up 2 hours (healthy)     0.0.0.0:80->80/tcp
myapp-api-1             myapp-api:v2.1.0        "uvicorn main:app --…"   api        2 hours ago     Up 2 hours (healthy)     0.0.0.0:8000->8000/tcp
myapp-worker-1          myapp-worker:v2.1.0     "celery -A tasks wor…"   worker     2 hours ago     Up 2 hours (running)
myapp-db-1              postgres:15             "docker-entrypoint.s…"   db         3 days ago      Up 3 days (healthy)      5432/tcp
myapp-redis-1           redis:7-alpine          "docker-entrypoint.s…"   redis      3 days ago      Up 3 days (healthy)      6379/tcp
"""

# ---------------------------------------------------------------------------
# docker compose ps — 4 services, 1 Restarting, 1 Exited
# ---------------------------------------------------------------------------

COMPOSE_PS_WITH_UNHEALTHY = """\
NAME                    IMAGE                   COMMAND                  SERVICE    CREATED         STATUS                   PORTS
myapp-web-1             myapp-web:latest        "/docker-entrypoint.…"   web        2 hours ago     Up 2 hours (healthy)     0.0.0.0:80->80/tcp
myapp-api-1             myapp-api:v2.1.0        "uvicorn main:app --…"   api        45 minutes ago  Restarting (1) 30s ago
myapp-db-1              postgres:15             "docker-entrypoint.s…"   db         3 days ago      Up 3 days (healthy)      5432/tcp
myapp-worker-1          myapp-worker:v2.1.0     "celery -A tasks wor…"   worker     10 minutes ago  Exited (137) 5 min ago
myapp-redis-1           redis:7-alpine          "docker-entrypoint.s…"   redis      3 days ago      Up 3 days (healthy)      6379/tcp
"""

# ---------------------------------------------------------------------------
# docker compose logs — 3 services, ~100 total log lines, 1 ERROR
# ---------------------------------------------------------------------------

COMPOSE_LOGS = """\
web-1     | 2026-04-13T10:00:00.001Z INFO  Starting nginx
web-1     | 2026-04-13T10:00:00.050Z INFO  Loading configuration
web-1     | 2026-04-13T10:00:00.100Z INFO  Configuration loaded successfully
web-1     | 2026-04-13T10:00:00.150Z INFO  Starting worker processes
web-1     | 2026-04-13T10:00:00.200Z INFO  nginx/1.25.3 started
web-1     | 2026-04-13T10:00:01.000Z INFO  Received GET /health
web-1     | 2026-04-13T10:00:01.010Z INFO  Health check passed: status=200
web-1     | 2026-04-13T10:00:02.000Z INFO  Received GET /
web-1     | 2026-04-13T10:00:02.050Z INFO  Request completed: GET / 200 12ms
web-1     | 2026-04-13T10:00:05.000Z INFO  Received POST /api/submit
web-1     | 2026-04-13T10:00:05.030Z INFO  Request completed: POST /api/submit 200 28ms
web-1     | 2026-04-13T10:00:10.000Z INFO  Received GET /static/app.js
web-1     | 2026-04-13T10:00:10.020Z INFO  Request completed: GET /static/app.js 304 3ms
web-1     | 2026-04-13T10:00:15.000Z INFO  Received GET /health
web-1     | 2026-04-13T10:00:15.010Z INFO  Health check passed: status=200
web-1     | 2026-04-13T10:00:20.000Z INFO  Received GET /api/users
web-1     | 2026-04-13T10:00:20.050Z INFO  Request completed: GET /api/users 200 45ms
web-1     | 2026-04-13T10:00:25.000Z INFO  Received GET /health
web-1     | 2026-04-13T10:00:25.010Z INFO  Health check passed: status=200
web-1     | 2026-04-13T10:00:30.000Z INFO  Received POST /api/login
web-1     | 2026-04-13T10:00:30.100Z INFO  Request completed: POST /api/login 200 98ms
api-1     | 2026-04-13T10:00:00.200Z INFO  Starting API server v2.1.0
api-1     | 2026-04-13T10:00:00.250Z INFO  Loading environment variables
api-1     | 2026-04-13T10:00:00.300Z INFO  Connecting to database
api-1     | 2026-04-13T10:00:00.450Z INFO  Database connection established
api-1     | 2026-04-13T10:00:00.500Z INFO  Initializing task queue
api-1     | 2026-04-13T10:00:00.600Z INFO  Task queue ready
api-1     | 2026-04-13T10:00:00.700Z INFO  API server ready on :8000
api-1     | 2026-04-13T10:00:01.100Z INFO  GET /health 200 1ms
api-1     | 2026-04-13T10:00:02.100Z INFO  GET /api/users 200 14ms
api-1     | 2026-04-13T10:00:05.100Z INFO  POST /api/submit 200 22ms
api-1     | 2026-04-13T10:00:10.000Z INFO  Processing background job job_id=job-001
api-1     | 2026-04-13T10:00:10.100Z INFO  Background job completed job_id=job-001
api-1     | 2026-04-13T10:00:15.100Z INFO  GET /health 200 1ms
api-1     | 2026-04-13T10:00:20.100Z INFO  GET /api/users 200 11ms
api-1     | 2026-04-13T10:00:25.000Z INFO  POST /api/orders 201 55ms
api-1     | 2026-04-13T10:00:28.000Z INFO  POST /api/orders 201 48ms
api-1     | 2026-04-13T10:00:29.900Z ERROR Failed to send confirmation email: SMTP connection refused
api-1     | 2026-04-13T10:00:29.901Z INFO  Queuing email for retry order_id=ord-789
api-1     | 2026-04-13T10:00:30.000Z INFO  Processing background job job_id=job-002
api-1     | 2026-04-13T10:00:30.100Z INFO  Background job completed job_id=job-002
api-1     | 2026-04-13T10:00:30.200Z INFO  POST /api/login 200 88ms
worker-1  | 2026-04-13T10:00:00.800Z INFO  Starting Celery worker
worker-1  | 2026-04-13T10:00:00.850Z INFO  Connected to Redis broker
worker-1  | 2026-04-13T10:00:00.900Z INFO  Worker ready, waiting for tasks
worker-1  | 2026-04-13T10:00:01.000Z INFO  Received task: send_email[task-001]
worker-1  | 2026-04-13T10:00:01.100Z INFO  Task send_email[task-001] succeeded in 0.08s
worker-1  | 2026-04-13T10:00:03.000Z INFO  Received task: process_upload[task-002]
worker-1  | 2026-04-13T10:00:03.200Z INFO  Task process_upload[task-002] succeeded in 0.19s
worker-1  | 2026-04-13T10:00:08.000Z INFO  Received task: send_report[task-003]
worker-1  | 2026-04-13T10:00:08.300Z INFO  Task send_report[task-003] succeeded in 0.28s
worker-1  | 2026-04-13T10:00:12.000Z INFO  Received task: cleanup_temp[task-004]
worker-1  | 2026-04-13T10:00:12.050Z INFO  Task cleanup_temp[task-004] succeeded in 0.04s
worker-1  | 2026-04-13T10:00:18.000Z INFO  Received task: generate_thumbnail[task-005]
worker-1  | 2026-04-13T10:00:18.400Z INFO  Task generate_thumbnail[task-005] succeeded in 0.38s
worker-1  | 2026-04-13T10:00:22.000Z INFO  Received task: send_email[task-006]
worker-1  | 2026-04-13T10:00:22.100Z INFO  Task send_email[task-006] succeeded in 0.09s
worker-1  | 2026-04-13T10:00:27.000Z INFO  Received task: index_document[task-007]
worker-1  | 2026-04-13T10:00:27.500Z INFO  Task index_document[task-007] succeeded in 0.48s
worker-1  | 2026-04-13T10:00:30.500Z INFO  Received task: send_email[task-008]
worker-1  | 2026-04-13T10:00:30.600Z INFO  Task send_email[task-008] succeeded in 0.09s
"""

# ---------------------------------------------------------------------------
# docker ps — 5 containers (3 running, 2 stopped/exited)
# ---------------------------------------------------------------------------

DOCKER_PS = """\
CONTAINER ID   IMAGE                   COMMAND                  CREATED         STATUS                     PORTS                    NAMES
a1b2c3d4e5f6   myapp-web:latest        "/docker-entrypoint.…"   2 hours ago     Up 2 hours                 0.0.0.0:80->80/tcp       myapp-web-1
b2c3d4e5f6a1   myapp-api:v2.1.0        "uvicorn main:app --…"   2 hours ago     Up 2 hours                 0.0.0.0:8000->8000/tcp   myapp-api-1
c3d4e5f6a1b2   postgres:15             "docker-entrypoint.s…"   3 days ago      Up 3 days                  5432/tcp                 myapp-db-1
d4e5f6a1b2c3   myapp-worker:v2.0.0     "celery -A tasks wor…"   5 hours ago     Exited (137) 3 hours ago                            myapp-worker-old
e5f6a1b2c3d4   redis:7-alpine          "docker-entrypoint.s…"   10 minutes ago  Exited (0) 5 minutes ago                            myapp-redis-test
"""

# ---------------------------------------------------------------------------
# docker images — 7 images from 4 repos
# ---------------------------------------------------------------------------

DOCKER_IMAGES = """\
REPOSITORY          TAG         IMAGE ID       CREATED         SIZE
myapp-web           latest      f1e2d3c4b5a6   2 hours ago     142MB
myapp-web           v2.1.0      a6b5c4d3e2f1   3 days ago      140MB
myapp-api           v2.1.0      9f8e7d6c5b4a   2 hours ago     318MB
myapp-api           v2.0.0      4a5b6c7d8e9f   5 days ago      315MB
postgres            15          1a2b3c4d5e6f   2 weeks ago     379MB
redis               7-alpine    6f5e4d3c2b1a   1 month ago     41.1MB
myapp-worker        v2.1.0      2b3c4d5e6f7a   2 hours ago     290MB
"""

# ---------------------------------------------------------------------------
# docker logs — ~85 timestamp-prefixed log lines with 2 ERRORs in middle
# ---------------------------------------------------------------------------

DOCKER_LOGS_SIMPLE = """\
2026-04-13T10:00:00.001Z INFO  Starting myapp-api v2.1.0
2026-04-13T10:00:00.050Z INFO  Loading configuration from environment
2026-04-13T10:00:00.100Z INFO  DATABASE_URL set
2026-04-13T10:00:00.150Z INFO  REDIS_URL set
2026-04-13T10:00:00.200Z INFO  Connecting to PostgreSQL at postgres:5432
2026-04-13T10:00:00.350Z INFO  PostgreSQL connection established
2026-04-13T10:00:00.400Z INFO  Connecting to Redis at redis:6379
2026-04-13T10:00:00.450Z INFO  Redis connection established
2026-04-13T10:00:00.500Z INFO  Initializing ORM models
2026-04-13T10:00:00.600Z INFO  Running database migrations
2026-04-13T10:00:00.800Z INFO  Migrations complete (3 applied)
2026-04-13T10:00:00.900Z INFO  Registering API routes
2026-04-13T10:00:00.950Z INFO  Registered: GET /health
2026-04-13T10:00:00.960Z INFO  Registered: GET /api/users
2026-04-13T10:00:00.970Z INFO  Registered: POST /api/users
2026-04-13T10:00:00.980Z INFO  Registered: GET /api/orders
2026-04-13T10:00:00.990Z INFO  Registered: POST /api/orders
2026-04-13T10:00:01.000Z INFO  Starting HTTP server on :8000
2026-04-13T10:00:01.100Z INFO  Server ready to accept connections
2026-04-13T10:00:01.200Z INFO  Health check endpoint registered at /health
2026-04-13T10:00:05.000Z INFO  GET /health 200 1ms
2026-04-13T10:00:10.000Z INFO  GET /api/users 200 15ms
2026-04-13T10:00:12.000Z INFO  POST /api/users 201 45ms
2026-04-13T10:00:15.000Z INFO  GET /health 200 1ms
2026-04-13T10:00:17.000Z INFO  GET /api/orders 200 22ms
2026-04-13T10:00:20.000Z INFO  POST /api/orders 201 67ms
2026-04-13T10:00:22.000Z INFO  GET /api/users 200 12ms
2026-04-13T10:00:25.000Z INFO  GET /health 200 1ms
2026-04-13T10:00:27.000Z INFO  POST /api/orders 201 71ms
2026-04-13T10:00:30.000Z INFO  GET /api/users 200 14ms
2026-04-13T10:00:32.000Z INFO  GET /api/orders 200 19ms
2026-04-13T10:00:35.000Z INFO  POST /api/users 201 52ms
2026-04-13T10:00:37.000Z INFO  GET /health 200 1ms
2026-04-13T10:00:40.000Z INFO  GET /api/orders 200 17ms
2026-04-13T10:00:42.000Z INFO  POST /api/orders 201 63ms
2026-04-13T10:00:44.000Z INFO  GET /api/users 200 11ms
2026-04-13T10:00:46.000Z INFO  Scheduled task: cleanup_expired_sessions
2026-04-13T10:00:46.100Z INFO  Deleted 12 expired sessions
2026-04-13T10:00:47.000Z INFO  GET /health 200 1ms
2026-04-13T10:00:50.000Z INFO  POST /api/orders 201 58ms
2026-04-13T10:00:52.000Z INFO  Processing payment for order ord-001
2026-04-13T10:00:52.100Z INFO  Calling payment gateway
2026-04-13T10:00:52.150Z ERROR Payment gateway timeout after 50ms: connection refused
2026-04-13T10:00:52.200Z INFO  Retrying payment gateway call attempt=2
2026-04-13T10:00:52.300Z INFO  Payment gateway returned 200 on retry
2026-04-13T10:00:55.000Z INFO  GET /api/users 200 13ms
2026-04-13T10:00:57.000Z INFO  GET /health 200 1ms
2026-04-13T10:01:00.000Z INFO  GET /api/orders 200 21ms
2026-04-13T10:01:02.000Z INFO  POST /api/users 201 49ms
2026-04-13T10:01:05.000Z INFO  POST /api/orders 201 60ms
2026-04-13T10:01:07.000Z INFO  GET /api/users 200 10ms
2026-04-13T10:01:10.000Z INFO  GET /health 200 1ms
2026-04-13T10:01:12.000Z INFO  GET /api/orders 200 18ms
2026-04-13T10:01:15.000Z INFO  POST /api/users 201 47ms
2026-04-13T10:01:17.000Z INFO  GET /api/users 200 12ms
2026-04-13T10:01:20.000Z INFO  POST /api/orders 201 55ms
2026-04-13T10:01:22.000Z INFO  Scheduled task: send_weekly_report
2026-04-13T10:01:22.050Z INFO  Fetching report data
2026-04-13T10:01:22.100Z INFO  Report data fetched: 247 rows
2026-04-13T10:01:22.150Z INFO  Generating PDF report
2026-04-13T10:01:22.250Z INFO  PDF generated: 14 pages
2026-04-13T10:01:22.300Z INFO  Sending report via email
2026-04-13T10:01:22.350Z ERROR SMTP connection failed: getaddrinfo ENOTFOUND smtp.example.com
2026-04-13T10:01:22.360Z INFO  Queuing email for retry report_id=rpt-2026-04-13
2026-04-13T10:01:22.400Z INFO  Email queued successfully
2026-04-13T10:01:25.000Z INFO  GET /health 200 1ms
2026-04-13T10:01:27.000Z INFO  GET /api/orders 200 23ms
2026-04-13T10:01:30.000Z INFO  POST /api/users 201 51ms
2026-04-13T10:01:32.000Z INFO  GET /api/users 200 11ms
2026-04-13T10:01:35.000Z INFO  POST /api/orders 201 62ms
2026-04-13T10:01:37.000Z INFO  GET /api/orders 200 20ms
2026-04-13T10:01:40.000Z INFO  GET /health 200 1ms
2026-04-13T10:01:42.000Z INFO  POST /api/orders 201 57ms
2026-04-13T10:01:45.000Z INFO  GET /api/users 200 14ms
2026-04-13T10:01:47.000Z INFO  Scheduled task: retry_failed_emails
2026-04-13T10:01:47.100Z INFO  Found 1 failed email to retry
2026-04-13T10:01:47.200Z INFO  Retry succeeded for report_id=rpt-2026-04-13
2026-04-13T10:01:50.000Z INFO  GET /health 200 1ms
2026-04-13T10:01:52.000Z INFO  POST /api/users 201 44ms
2026-04-13T10:01:55.000Z INFO  GET /api/orders 200 17ms
2026-04-13T10:01:57.000Z INFO  Received SIGTERM signal
2026-04-13T10:01:57.010Z INFO  Graceful shutdown initiated
2026-04-13T10:01:57.100Z INFO  Stopping HTTP server
2026-04-13T10:01:57.200Z INFO  Waiting for in-flight requests to complete
2026-04-13T10:01:57.500Z INFO  All requests completed
2026-04-13T10:01:57.600Z INFO  Closing database connection
2026-04-13T10:01:57.700Z INFO  Shutdown complete
"""
