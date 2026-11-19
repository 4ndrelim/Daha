/** The web switch for the handoff coordinator (the server also needs HANDOFF_COORDINATOR_ENABLED=true). */
export const HANDOFF_COORDINATOR = process.env.NEXT_PUBLIC_HANDOFF_COORDINATOR?.trim().toLowerCase() === "true";
