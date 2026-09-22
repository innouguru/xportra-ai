# Configuration Contract — Xportra AI

> Minimal configuration contract. Variable names only — no secret values
> are recorded here or anywhere in documentation.
> Status: canonical schema established in
> `docs/architecture/environment-schema.md`.

## Canonical specification

The authoritative variable-level specification for Xportra AI is
`docs/architecture/environment-schema.md`. This document defines the
approved names and their intended purpose; it is the canonical reference
for environment configuration.

## Observed inherited state

- The existing `.env` was inspected by variable NAME only (values never
  read, printed, or copied).
- The inherited name `OPENROUTER_API_KEY` was identified as legacy RAG
  course configuration and is not an approved Xportra AI variable.
- The inherited name was removed from the local `.env` in favor of the
  canonical Xportra AI schema under `LLM_API_KEY`.

## Approved categories

No specific providers or production infrastructure are selected. The schema
is intentionally minimal and provider-neutral.

### 1. Application environment

- Variables: `APP_ENV`, `APP_NAME`, `APP_DEBUG`
- Purpose: runtime context and application identity.

### 2. Database configuration

- Variable: `DATABASE_URL`
- Purpose: connection string for the primary persistence layer.

### 3. Vector store configuration

- Variables: `VECTOR_STORE_URL`, `VECTOR_STORE_COLLECTION`
- Purpose: retrieval store endpoint and namespace.

### 4. LLM configuration

- Variables: `LLM_API_KEY`, `LLM_MODEL`
- Purpose: secret credential and model identifier for the selected LLM.

### 5. Embedding configuration

- Variable: `EMBEDDING_MODEL`
- Purpose: model identifier used for embedding generation.

### 6. Observability configuration

- Variable: `LOG_LEVEL`
- Purpose: runtime logging verbosity.

## Rules

- The canonical, variable-level specification is
  `docs/architecture/environment-schema.md`.
- `.env.example` is the repository-authoritative template for required
  environment configuration.
- `.env` contains local environment values and secrets and must never be
  committed.
- Provider selection remains explicitly unresolved; no provider-specific
  variables are approved by this contract.
