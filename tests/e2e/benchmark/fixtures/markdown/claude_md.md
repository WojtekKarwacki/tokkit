# MyProject

A production SaaS application for team collaboration with real-time features.

## Project Structure

- `src/api/` — REST API endpoints (Express.js)
- `src/services/` — Business logic layer
- `src/models/` — Database models (Prisma ORM)
- `src/middleware/` — Auth, rate limiting, validation
- `src/workers/` — Background job processors
- `src/realtime/` — WebSocket handlers
- `packages/shared/` — Shared types and utilities
- `packages/ui/` — Component library (React)
- `apps/web/` — Next.js frontend
- `apps/mobile/` — React Native mobile app
- `infra/` — Terraform + Docker configs

## Running

```bash
# Install dependencies
pnpm install

# Development (all services)
pnpm dev

# Individual services
pnpm dev:api          # API server on :3001
pnpm dev:web          # Web frontend on :3000
pnpm dev:workers      # Background workers

# Database
pnpm db:migrate       # Run migrations
pnpm db:seed          # Seed development data
pnpm db:studio        # Open Prisma Studio

# Tests
pnpm test             # All tests
pnpm test:api         # API integration tests
pnpm test:e2e         # Playwright E2E tests
pnpm test:unit        # Unit tests only
```

## Architecture Decisions

### Authentication

We use Clerk for authentication. User sessions are validated via JWT middleware on every API request. The `src/middleware/auth.ts` file handles token verification and attaches the user object to the request context.

**Important:** Never use `getAuth()` directly in services. Always access the user through the request context passed from middleware. This keeps services testable and decoupled from the auth provider.

### Database

PostgreSQL via Prisma ORM. All queries go through the service layer, never directly from route handlers.

**Conventions:**
- Soft deletes everywhere (use `deletedAt` timestamp)
- All tables have `createdAt` and `updatedAt`
- Use Prisma transactions for multi-table operations
- Never use raw SQL unless Prisma can't express the query

### Real-time

WebSocket connections managed by Socket.io with Redis adapter for horizontal scaling. Channels follow the pattern `{resource}:{id}` (e.g., `workspace:abc123`).

**Event naming:** `{resource}.{action}` (e.g., `message.created`, `document.updated`)

### Background Jobs

BullMQ with Redis. Jobs are defined in `src/workers/` and registered in `src/workers/index.ts`.

**Retry policy:** 3 retries with exponential backoff (1s, 4s, 16s). Failed jobs go to dead letter queue after all retries exhausted.

### Caching

Redis caching with a TTL-based strategy. Cache keys follow `{service}:{resource}:{id}` pattern.

**Cache invalidation:** Event-driven via the service layer. When a resource is updated, the service emits an event that triggers cache invalidation.

## API Conventions

### Request/Response Format

All API responses follow this envelope:

```typescript
// Success
{
  "data": T,
  "meta": { "page": number, "total": number }  // for paginated
}

// Error
{
  "error": {
    "code": string,
    "message": string,
    "details": object | null
  }
}
```

### Pagination

Cursor-based pagination for all list endpoints. Use `cursor` and `limit` query params.

```
GET /api/messages?cursor=msg_abc123&limit=50
```

### Rate Limiting

- Authenticated: 1000 req/min per user
- Unauthenticated: 60 req/min per IP
- File uploads: 10 req/min per user
- WebSocket messages: 30 msg/sec per connection

Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `unauthorized` | 401 | Missing or invalid auth token |
| `forbidden` | 403 | Valid auth but insufficient permissions |
| `not_found` | 404 | Resource does not exist |
| `conflict` | 409 | Resource already exists or state conflict |
| `rate_limited` | 429 | Too many requests |
| `validation_error` | 422 | Invalid request body |
| `internal_error` | 500 | Unexpected server error |

## Testing Strategy

### Unit Tests

Located alongside source files as `*.test.ts`. Mock external dependencies (database, cache, external APIs).

```bash
pnpm test:unit
```

### Integration Tests

Located in `tests/integration/`. Use a real test database (Docker Compose spins it up). Tests run against the actual API with real HTTP requests.

```bash
pnpm test:api
```

**Important:** Integration tests use transactions that roll back after each test. Do not rely on data from previous tests.

### E2E Tests

Playwright tests in `tests/e2e/`. Test critical user flows through the actual UI.

```bash
pnpm test:e2e
```

### Test Data

Use factories in `tests/factories/` to create test data. Never hardcode IDs or use magic strings.

```typescript
const user = await UserFactory.create({ role: "admin" });
const workspace = await WorkspaceFactory.create({ ownerId: user.id });
```

## Deployment

### Environments

| Environment | Branch | URL | Database |
|-------------|--------|-----|----------|
| Development | `develop` | dev.myproject.io | dev-db |
| Staging | `staging` | staging.myproject.io | staging-db |
| Production | `main` | app.myproject.io | prod-db |

### CI/CD Pipeline

GitHub Actions handles all CI/CD:

1. **PR checks:** Lint, type check, unit tests, integration tests
2. **Merge to develop:** Deploy to dev environment
3. **Merge to staging:** Deploy to staging + run E2E tests
4. **Merge to main:** Deploy to production (requires approval)

### Infrastructure

- **Compute:** AWS ECS Fargate
- **Database:** AWS RDS PostgreSQL
- **Cache:** AWS ElastiCache Redis
- **Storage:** AWS S3
- **CDN:** CloudFront
- **DNS:** Route53
- **Monitoring:** Datadog
- **Error tracking:** Sentry

### Environment Variables

Required environment variables for each service:

```
# API
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
CLERK_SECRET_KEY=sk_...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=...

# Web
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
NEXT_PUBLIC_API_URL=https://...
NEXT_PUBLIC_WS_URL=wss://...
```

## Code Style

- **Formatter:** Prettier (runs on save)
- **Linter:** ESLint with strict TypeScript rules
- **Imports:** Absolute imports from `@/` prefix
- **Naming:** camelCase for variables/functions, PascalCase for types/components
- **Files:** kebab-case for file names, PascalCase for React components

### Commit Messages

Follow Conventional Commits:

```
feat: add workspace invitation flow
fix: prevent duplicate webhook deliveries
refactor: extract auth middleware into separate module
```

### PR Process

1. Create branch from `develop`
2. Write code + tests
3. Open PR with description
4. Automated checks must pass
5. One approval required
6. Squash merge into `develop`
