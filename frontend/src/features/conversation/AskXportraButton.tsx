import { useConversation, type AskSeed } from "./ConversationContext";

/**
 * Consistent "Ask Xportra" entry point. Opens the shared
 * shipment-scoped conversation panel with the given seed;
 * it never sends anything by itself.
 */
export function AskXportraButton({
  seed,
  label = "Ask Xportra",
  className = "ghost-button",
}: {
  seed?: AskSeed;
  label?: string;
  className?: string;
}) {
  const { openAsk } = useConversation();
  return (
    <button type="button" className={className} onClick={() => openAsk(seed)}>
      {label}
    </button>
  );
}
