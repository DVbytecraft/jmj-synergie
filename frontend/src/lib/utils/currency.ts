/**
 * Format cents to human-readable currency string.
 * Stored as integer cents (e.g. 150000 = 1 500 XAF).
 */
export function formatCents(cents: number, currency = "XAF"): string {
  const amount = cents / 100;
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    minimumFractionDigits: currency === "XAF" ? 0 : 2,
    maximumFractionDigits: currency === "XAF" ? 0 : 2,
  }).format(amount);
}

export function centsToDecimal(cents: number): number {
  return cents / 100;
}

export function decimalToCents(amount: number): number {
  return Math.round(amount * 100);
}
