# Infrastructure migration and production checklist

## Current changes

- FAISS remains the default (`VECTOR_STORE=faiss`) and rollback path.
- Setting `VECTOR_STORE=qdrant` routes dense retrieval through Qdrant while the
  existing BM25 corpus remains a local JSON file.
- New documents are embedded and upserted by document into Qdrant. Deletion
  removes points by `document_id`; it does not rebuild the dense collection.
- `STORAGE_BACKEND=s3` stores PDFs in a private S3-compatible bucket; `local`
  remains the default for existing local development environments. Configure
  `S3_BUCKET`, optional `S3_ENDPOINT_URL`, `S3_REGION`, and credentials (or
  use the AWS workload identity chain).
- Upload and reprocess requests enqueue Celery tasks through `CELERY_BROKER_URL`.
  The worker retries failures up to three times with exponential backoff, while
  SQL processing-job rows remain the source of status and progress.
- Redis-backed request limits cover login (10/min/IP), registration
  (5/hour/IP), uploads (20/hour/user and 60/hour/IP), and chat
  (30/min/user and 90/min/IP). Compose enables the limiter and API startup fails
  if Redis cannot be reached; non-Compose local runs can enable it with
  `RATE_LIMIT_ENABLED=true`.
- Access tokens expire after 15 minutes. Refresh tokens are opaque, stored only
  as SHA-256 hashes, rotated at refresh, and revoked as a family on detected
  reuse or logout. Refresh cookies are `HttpOnly`; refresh/logout require a
  double-submit CSRF token. The default cookie policy is `SameSite=None; Secure`
  for cross-site deployments. The Compose defaults are local-development-only
  (`SameSite=Lax`, insecure HTTP); set `REFRESH_COOKIE_SECURE=true` and
  `REFRESH_COOKIE_SAMESITE=none` behind HTTPS in production.
- `DELETE /api/auth/me` requires the current password and removes the account,
  SQL-owned data, uploaded files, local indexes, and per-knowledge-base Qdrant
  collections. External cleanup is performed before SQL deletion so a failure
  leaves an account that can retry; cleanup operations are idempotent.
- Run `docker compose up -d` for local Qdrant, Redis, MinIO, API, and worker
  services. Set `DATABASE_URL` and `JWT_SECRET_KEY` in the Compose environment.
  The bundled MinIO credentials are local-development defaults only.
- Apply database migrations before starting the new API/worker version:

  ```sh
  cd backend
  alembic upgrade head
  ```

  For the Compose image, run `docker compose run --rm api alembic upgrade head`
  as a release step before replacing the API/worker containers.

- Migrate existing local PDF files before switching existing records to S3:

  ```sh
  cd backend
  STORAGE_BACKEND=s3 python -m scripts.migrate_local_uploads_to_s3 --confirm
  ```

  The script updates each database path only after its object upload succeeds.
  Keep local files until the S3 copy and authenticated download path have been
  verified.
- For a remote Qdrant service, set `QDRANT_URL` and `QDRANT_API_KEY` in the
  backend environment.
- Migrate an existing knowledge base with:

  ```sh
  cd backend
  VECTOR_STORE=qdrant python -m scripts.migrate_faiss_to_qdrant KNOWLEDGE_BASE_ID --confirm
  ```

The Qdrant collection stores one dense vector per chunk and payload keys for
`chunk_id` and `document_id`. BM25 is currently retained for the keyword side;
this migration does not claim to have moved sparse BM25 vectors into Qdrant.

## Rollback

1. Stop document uploads/processing during a migration or rollback window.
2. Keep the original FAISS files and database backups until Qdrant results are
   validated for representative queries.
3. To roll back, set `VECTOR_STORE=faiss`, restart the backend, and verify that
   each knowledge base still has its FAISS files. FAISS ingestion continues to
   rebuild its index from database chunks.
4. Do not remove Qdrant data or its volume until the rollback window closes and
   a database/vector-store backup has been tested.
5. Resume uploads only after confirming the configured vector store and index
   contents. Database chunks remain the source of truth.

## Remaining production migration work

These are not implemented by the current Qdrant adapter and need staged rollout:

- **Sparse search:** evaluate Qdrant sparse vectors (for example, a versioned
  sparse encoder) against current BM25 before removing local BM25 JSON. Preserve
  a shadow-query period and compare Recall@5/MRR.
- **Object storage:** configure S3-compatible storage in production and migrate
  existing local uploads. Downloads are proxied through the authenticated API;
  short-lived signed URLs are not exposed to clients.
- **Durable ingestion queue:** jobs now use the included Celery/Redis worker,
  persist status/progress, and retry up to three times. A transactional
  outbox/recovery scan is still needed to close
  the narrow failure window between committing a job row and publishing to
  Redis.
- **Rate limiting:** tune the included Redis-backed limits from observed staging
  traffic and verify the reverse-proxy client-IP configuration before rollout.
- **Refresh tokens:** password-change revocation and periodic cleanup of
  expired token records are still outstanding. Existing access tokens remain
  valid until their short expiration; logout revokes refresh sessions, not
  already-issued access JWTs.
- **Tenant deletion:** extend tests to cover S3 and remote-Qdrant partial
  failures, pending-job races, and cleanup retries in staging.
- **Isolation tests:** current tests cover document/file and conversation
  ownership. Add coverage for feedback, subjects, and indexed knowledge-base
  queries across accounts.
- **Secrets:** `.gitignore` excludes `.env` and `.env.*`, but this workspace has
  no Git metadata to verify whether any local environment file was committed
  previously. Check repository history and rotate any credentials that may
  have been exposed; use deployment secret stores. Never put Qdrant or LLM
  secrets in the frontend.

## Deployment checklist

- Use a managed SQL database with TLS, backups, and tested restore procedures.
- Deploy the backend in Docker on a persistent VM/container platform; provision
  object storage, Redis, and Qdrant as private services with authentication and
  network restrictions.
- Deploy only the static frontend on Vercel; configure the API URL and CORS
  allowlist for the production origin.
- Pin and scan images/dependencies; run migrations as a release step, not on
  every worker start.
- Configure HTTPS, non-debug mode, strong JWT secrets, request-size limits,
  upload magic-byte validation, structured logs, health checks, and alerts.
- Back up SQL, PDFs, Qdrant snapshots, and Redis job state as appropriate; run
  restore and account-deletion drills before accepting user data.
- Verify upload validation, per-user isolation, rate limits, refresh-token
  rotation, document deletion, and Qdrant rollback in staging.
