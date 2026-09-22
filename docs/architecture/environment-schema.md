# Environment Schema — Xportra AI

> Canonical environment-variable contract for Xportra AI.
> This document defines the approved variable names and their intended use.
> It is the source for the variable-level configuration contract; provider
> selection remains intentionally unresolved.

## Canonical variables

The schema is intentionally minimal, provider-neutral, and limited to the
required runtime categories. No additional variables are introduced unless a
future approved task demonstrates a concrete need.

### Application

#### APP_ENV
- Purpose: identifies the runtime environment, such as development, test, or production.
- Required: yes, for local runtime context.
- Secret: no.
- Type/format: string; expected values such as `development`, `test`, or `production`.
- Example: `development`

#### APP_NAME
- Purpose: names the application instance for logs, diagnostics, and local configuration.
- Required: yes.
- Secret: no.
- Type/format: string.
- Example: `xportra-ai`

#### APP_DEBUG
- Purpose: enables or disables debug behavior for local diagnostics.
- Required: no, but recommended in development.
- Secret: no.
- Type/format: boolean; use `true` or `false`.
- Example: `true`

### Database

#### DATABASE_URL
- Purpose: connection string for the primary data store.
- Required: yes when the persistence layer is configured.
- Secret: possibly, depending on the selected database setup; the value is treated as a secret store entry if credentials are included.
- Type/format: connection-string/URL. The specific driver or engine is not selected here.
- Example placeholder: `database://user:password@host:port/database_name`

### Authentication (Supabase Auth)

Supabase is the approved authentication provider (Phase 0.5 technology
baseline). These variables configure server-side verification of Supabase Auth
access tokens and are only required on deployments that authenticate requests.

#### SUPABASE_URL
- Purpose: Supabase project URL. When provided, it enables issuer verification
  of Supabase Auth access tokens (`<url>/auth/v1`).
- Required: no. Recommended to enable issuer verification.
- Secret: no.
- Type/format: URL.
- Example placeholder: `https://project-ref.supabase.co`

#### SUPABASE_JWT_SECRET
- Purpose: the Supabase project JWT secret used to verify the HS256 signature
  of Supabase Auth access tokens.
- Required: yes when authentication is enabled.
- Secret: yes. Must be supplied through environment/secret configuration and
  never written into source code or documentation.
- Type/format: secret string.
- Example placeholder: `replace-with-supabase-jwt-secret`

#### SUPABASE_JWT_AUDIENCE
- Purpose: expected `aud` claim of Supabase Auth access tokens. Defaults to
  `authenticated`, matching the default Supabase JWT audience.
- Required: no.
- Secret: no.
- Type/format: string.
- Example: `authenticated`

### Vector store

#### VECTOR_STORE_URL
- Purpose: connection endpoint for the vector store used for retrieval.
- Required: yes when the vector store is configured.
- Secret: possibly, depending on the selected deployment; values may include credentials and must be stored as local secrets.
- Type/format: URL or service endpoint.
- Example placeholder: `https://vector-store.example.internal`

#### VECTOR_STORE_COLLECTION
- Purpose: names the collection or namespace used within the vector store.
- Required: yes when the vector store is configured.
- Secret: no.
- Type/format: string.
- Example: `xportra-documents`

### LLM

#### LLM_API_KEY
- Purpose: API key for the selected LLM provider.
- Required: yes when an LLM call is enabled.
- Secret: yes.
- Type/format: secret string or token value supplied by the provider.
- Example placeholder: `replace-with-llm-api-key`

#### LLM_MODEL
- Purpose: model identifier for the LLM used for reasoning or generation.
- Required: yes when an LLM call is enabled.
- Secret: no.
- Type/format: string model identifier.
- Example placeholder: `model-name`

### Embeddings

#### EMBEDDING_MODEL
- Purpose: model identifier used for embedding generation.
- Required: yes when embeddings are enabled.
- Secret: no.
- Type/format: string model identifier.
- Example placeholder: `embedding-model-name`

### Observability

#### LOG_LEVEL
- Purpose: logging verbosity for local and operational diagnostics.
- Required: no, but recommended.
- Secret: no.
- Type/format: string; expected values are `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
- Example: `INFO`

## Repository authority

- `.env.example` is the repository-authoritative template for required environment configuration.
- `.env` is the local environment file for secrets and machine-specific configuration and must not be committed.
- This schema is intentionally provider-neutral and remains compatible with future provider selection work, which is explicitly deferred.
- No provider-specific configuration variables are approved by this schema.
