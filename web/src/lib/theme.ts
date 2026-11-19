/**
 * The one switch for the holiday look. Set NEXT_PUBLIC_THEME=classic in web/.env.local
 * (then restart `make web`) to go back to the emerald + amber DAHA colors.
 * The colors themselves live in globals.css under [data-theme="holiday"].
 */
export type Theme = "holiday" | "classic";

export const THEME: Theme = process.env.NEXT_PUBLIC_THEME?.trim().toLowerCase() === "classic" ? "classic" : "holiday";

/** Page background per theme: the browser bar and the installed app's splash screen use it. */
export const BACKGROUND: Record<Theme, string> = { classic: "#fafaf9", holiday: "#fffaf3" };
