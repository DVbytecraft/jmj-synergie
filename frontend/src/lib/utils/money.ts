/** Converts an amount in cents (integer) to a display-ready number. */
export function centsToAmount(cents: number): number {
  return cents / 100;
}

/** Converts a decimal amount to cents (integer). */
export function amountToCents(amount: number): number {
  return Math.round(amount * 100);
}

export function formatMoney(amount: number, currency = "XAF"): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Format directly from cents. */
export function formatCents(cents: number, currency = "XAF"): string {
  return formatMoney(centsToAmount(cents), currency);
}
