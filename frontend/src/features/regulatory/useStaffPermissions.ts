import { useIdentity } from "../../app/IdentityContext";

/**
 * Convenience view over the server-resolved staff grants.
 *
 * This only shapes the UI: when the person lacks a grant the matching
 * decision form is replaced by a short explanation instead of letting
 * them type a rationale and meet a 403. The server still authorizes
 * every action. When identity is not (yet) known, nothing is hidden
 * (``mayAttempt`` is true) so the server remains the single authority.
 */
export function useStaffPermissions() {
  const { identity, status } = useIdentity();
  const known = status === "ready" && identity !== null;
  return {
    known,
    mayAttempt(permission: string): boolean {
      return !known || (identity?.staff_permissions ?? []).includes(permission);
    },
  };
}
