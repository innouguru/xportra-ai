/**
 * Typed conversational endpoint.
 *
 * Exactly one route exists (`conversations.py`):
 * - POST /conversations/messages (member-readable)
 *
 * The function transports one stateless, read-only turn
 * and surfaces backend errors unchanged. No compliance
 * logic lives here: intent, mode, and context rules are
 * enforced by the backend, which revalidates the
 * workflow record per request and holds no session.
 * Nothing here can mutate, persist, or propose actions.
 */

import { apiFetch, type AuthCredentials } from "./client";
import type {
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
