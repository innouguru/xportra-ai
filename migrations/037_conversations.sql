BEGIN;

CREATE TABLE xportra.conversations (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE CASCADE,
    mode TEXT NOT NULL
        CHECK (mode IN ('shipment_aware', 'knowledge')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX conversations_tenant_updated_idx
    ON xportra.conversations (tenant_id, updated_at DESC);

CREATE TABLE xportra.conversation_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL
        REFERENCES xportra.conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL
        CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    intent TEXT,
    status TEXT,
    citations JSONB NOT NULL DEFAULT '[]',
    shipment_references JSONB NOT NULL DEFAULT '[]',
    refusal_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX conversation_messages_conversation_created_idx
    ON xportra.conversation_messages (conversation_id, created_at);

COMMIT;
