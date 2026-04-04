/**
 * Calculate reliability stars based on data years and trial count.
 *
 * Free (2yr): max 2 stars, decreases with trials
 * Pro (5yr):  max 5 stars, decreases with trials
 */
export function calculateReliability(dataYears: number, trialCount: number): number {
  let base = dataYears <= 2 ? 2 : Math.min(5, Math.floor(dataYears));

  if (trialCount > 20) base = Math.max(1, base - 1);
  if (trialCount > 10) base = Math.max(1, base - 1);

  return Math.max(1, Math.min(5, base));
}
