/**
 * Typed conversational endpoints.
 *
 * Conversation lifecycle:
 * - POST /conversations                  Create a conversation
 * - GET  /conversations                  List the tenant's conversations
 * - GET  /conversations/{conversation_id}  Get a conversation with messages
 * - POST /conversations/messages         Send one turn
 *
 * Tenant identity always comes from server-resolved membership;
 * the client never supplies tenant IDs. Conversation IDs are
 * client-generated correlation identifiers echoed by the backend.
 * Nothing here can mutate compliance state.
 */

import { apiFetch, type AuthCredentials } from "./client";
import type {
  ConversationCreateRequest,
  ConversationCreateResponse,
  ConversationDetailResponse,
  ConversationListResponse,
  ConversationMessageRequest,
  ConversationMessageResponse,
} from "../types/api";

export function postConversationMessage(
  credentials: AuthCredentials,
  input: ConversationMessageRequest,
): Promise<ConversationMessageResponse> {
  return apiFetch<ConversationMessageResponse>(
    "/conversations/messages",
    credentials,
    { method: "POST", body: input },
  );
}

export function createConversation(
  credentials: AuthCredentials,
  input: ConversationCreateRequest,
): Promise<ConversationCreateResponse> {
  return apiFetch<ConversationCreateResponse>(
    "/conversations",
    credentials,
    { method: "POST", body: input },
  );
}

export function listConversations(
  credentials: AuthCredentials,
): Promise<ConversationListResponse> {
  return apiFetch<ConversationListResponse>(
    "/conversations",
    credentials,
    { method: "GET" },
  );
}

export function getConversation(
  credentials: AuthCredentials,
  conversationId: string,
): Promise<ConversationDetailResponse> {
  return apiFetch<ConversationDetailResponse>(
    `/conversations/${encodeURIComponent(conversationId)}`,
    credentials,
    { method: "GET" },
  );
}
