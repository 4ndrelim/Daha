/** The web switch for "Condition check" (the server also needs CONDITION_CHECK_ENABLED=true). */
export const CONDITION_CHECK = process.env.NEXT_PUBLIC_CONDITION_CHECK?.trim().toLowerCase() === "true";
