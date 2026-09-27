import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { ConversationIntent, ConversationMode } from "../../types/api";

/**
 * Seed for opening the Ask Xportra panel with relevant
 * context. Seeds carry identifiers and a suggested
 * question only — the backend revalidates everything
 * per request and the user always confirms by sending.
 */
export interface AskSeed {
  mode?: ConversationMode;
  intent?: ConversationIntent;
  requirementId?: string;
  evidenceId?: string;
  suggestedText?: string;
  focus?: "shipment" | "requirement" | "gap" | "finding" | "evidence";
}

interface ConversationPanelState {
  open: boolean;
  seed: AskSeed;
  openAsk: (seed?: AskSeed) => void;
  close: () => void;
}

const ConversationContext = createContext<ConversationPanelState | null>(null);

export function ConversationProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [seed, setSeed] = useState<AskSeed>({});

  const openAsk = useCallback((next?: AskSeed) => {
    setSeed(next ?? {});
    setOpen(true);
  }, []);

  const close = useCallback(() => {
    setOpen(false);
  }, []);

  const value = useMemo(
    () => ({ open, seed, openAsk, close }),
    [open, seed, openAsk, close],
  );
  return <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>;
}

export function useConversation(): ConversationPanelState {
  const state = useContext(ConversationContext);
  if (state === null) {
    throw new Error("useConversation must be used inside <ConversationProvider>");
  }
  return state;
}
