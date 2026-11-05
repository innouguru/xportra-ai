BEGIN;

DROP INDEX IF EXISTS xportra.conversation_messages_conversation_created_idx;
DROP INDEX IF EXISTS xportra.conversations_tenant_updated_idx;
DROP TABLE IF EXISTS xportra.conversation_messages;
DROP TABLE IF EXISTS xportra.conversations;

COMMIT;
