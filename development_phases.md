Phase 0 — Agent Harness & Project Foundation

Before implementing business functionality.

We establish:

repository structure
engineering rules
architecture specification
task system
project state
decision records
testing strategy
quality gates
agent instructions
context-recovery mechanism
development commands
environment configuration
FastAPI foundation
PostgreSQL
Alembic
health endpoints
initial Shipment model/migration

This corresponds to the foundation we had already identified.

The agent should not start building AgriClear's intelligence before this phase is stable.

3. Phase 1 — Core Domain & Database

Build the deterministic business foundation.

The agent implements:

shipment domain
users/roles where required
commodities
origins/destinations
regulatory jurisdictions
documents
requirements
compliance-related entities
database relationships
constraints
migrations
repositories/services

The important principle here is:

Business truth lives in structured data, not inside the LLM.

This becomes extremely important later.

Gate

Before moving on:

migrations work from a clean database
models satisfy domain invariants
repository/service tests pass
no business logic is hiding inside API handlers
no LLM dependency exists in this phase
4. Phase 2 — Knowledge Ingestion

Now we build the knowledge pipeline.

Source
  ↓
Document acquisition
  ↓
Document storage
  ↓
Parsing
  ↓
OCR when required
  ↓
Normalization
  ↓
Metadata extraction
  ↓
Chunking
  ↓
Knowledge representation

This phase establishes how AgriClear gets regulatory/operational knowledge into the system.

The agent should build this incrementally rather than immediately constructing the complete RAG pipeline.

Gate

We need ingestion tests covering things like:

valid document
malformed document
duplicate document
OCR-required document
parsing failure
metadata failure
unsupported document
partial ingestion
5. Phase 3 — Deterministic Applicability Engine

This is one of the most important architectural boundaries.

AgriClear must first determine:

Which requirements apply to this shipment?

before asking an LLM to reason over evidence.

For example:

Shipment
   ↓
Commodity
   ↓
Origin
   ↓
Destination
   ↓
Transport / shipment attributes
   ↓
Applicable regulations
   ↓
Applicable requirements

The applicability engine should be deterministic wherever possible.

The LLM should not decide fundamental applicability merely because a retrieved document "sounds relevant."

Gate

We create explicit applicability test cases:

Shipment A → Requirements X, Y
Shipment B → Requirements X, Z
Shipment C → No requirement Z

And regression tests prevent later RAG changes from silently changing applicability.

6. Phase 4 — Document Intelligence & Evidence Matching

Now we connect requirements to documents/evidence.

Example:

Requirement
     ↓
Required evidence
     ↓
Uploaded document
     ↓
Extraction
     ↓
Evidence matching
     ↓
Satisfied / Missing / Unclear

This is where document intelligence becomes useful.

But we maintain another critical boundary:

Deterministic applicability
          ≠
Evidence interpretation

The LLM may help interpret documents, but it does not redefine the regulatory universe.

Gate

Test:

correct document
wrong document
missing document
ambiguous document
incomplete evidence
conflicting evidence
extraction failure
unsupported evidence
7. Phase 5 — Retrieval & RAG

Only now do we build the actual RAG layer.

The architecture becomes roughly:

User / Workflow
      ↓
Query construction
      ↓
Metadata filtering
      ↓
Vector / keyword retrieval
      ↓
Reranking
      ↓
Context selection
      ↓
LLM
      ↓
Grounded response
      ↓
Citations / evidence

This is where Qdrant comes in.

But the retrieval system should operate within the boundaries established by the applicability engine.

We also introduce:

retrieval evaluation
golden questions
precision/recall testing
citation validation
hallucination tests
retrieval regression tests
8. Phase 6 — Compliance Reasoning & Decision Support

Now we combine:

Shipment
     +
Applicable requirements
     +
Evidence
     +
Knowledge retrieval
     ↓
Compliance analysis

The output should be something like:

Requirement
Status
Evidence
Source
Reason
Missing information
Confidence / uncertainty

Not simply:

"Your shipment is compliant."

The system should expose why it reached an assessment.

This is a major part of making AgriClear a real product rather than a RAG demo.

9. Phase 7 — User Workflow

Now we construct the actual user journey.

For example:

Create shipment
      ↓
Provide shipment information
      ↓
Upload documents
      ↓
System determines applicable requirements
      ↓
System identifies missing evidence
      ↓
Documents are analyzed
      ↓
Compliance analysis
      ↓
User reviews findings
      ↓
Resolve issues / upload additional evidence
      ↓
Final assessment package

This is where the individual components become a coherent application.

10. Phase 8 — API & Application Integration

Then we expose the system through a proper API.

Potential boundaries:

/auth
/shipments
/documents
/requirements
/evidence
/compliance
/search
/analysis

The exact API will be determined from the domain rather than invented prematurely.

At this point:

API
 ↓
Application services
 ↓
Domain logic
 ↓
PostgreSQL / Qdrant / storage / workers / LLM

We should avoid:

API endpoint
   ↓
50 lines of business logic
   ↓
LLM call
11. Phase 9 — Evaluation & Reliability

This phase is not simply "run a few questions."

We establish a proper evaluation system.

Retrieval
Precision@K
Recall@K
MRR
citation correctness
Extraction
field-level accuracy
document classification accuracy
evidence matching accuracy
Compliance reasoning
groundedness
requirement coverage
unsupported claims
contradiction handling
System
latency
failures
retries
rate limits
resource usage
cost

And most importantly:

Regression protection

Every important bug we discover becomes a test.

Bug discovered
      ↓
Reproduce
      ↓
Write regression test
      ↓
Fix
      ↓
Test permanently remains

This means the agent cannot repeatedly reintroduce old mistakes.

12. Phase 10 — Production Hardening

Finally:

authentication
authorization
tenant isolation
secrets
rate limiting
observability
background jobs
persistent storage
failure handling
retries
migrations
deployment
monitoring
alerts
rollback
cost controls

This corresponds closely to what we learned in the RAG course, but now we apply it to a real system rather than learning the concepts abstractly.


Finish 1.10
↓
Phase 2 — Knowledge Ingestion
↓
Phase 3 — Applicability Engine
↓
Phase 4 — Document Intelligence & Evidence Matching
↓
Phase 5 — Retrieval & RAG
↓
Phase 6 — Compliance Reasoning & Decision Support
↓

PAUSE AND DESIGN THE UI/USER WORKFLOW

↓
Phase 7 onward