/**
 * Format cents to human-readable currency string.
 * Stored as integer cents (e.g. 150000 = 1 500 XAF).
 *
 * Règles de décimales par devise :
 *   - XAF, GNF : pas de décimales (pas de centimes dans ces devises)
 *   - EUR, USD, GHS, MAD, NGN : 2 décimales standard
 */

// Devises sans décimales (FCFA, Franc guinéen, Naira arrondi ici par convention OHADA)
const ZERO_DECIMAL_CURRENCIES = new Set(["XAF", "GNF"]);

export function getDecimalPlaces(currency: string): 0 | 2 {
  return ZERO_DECIMAL_CURRENCIES.has(currency.toUpperCase()) ? 0 : 2;
}

export function formatAmount(cents: number, currency = "XAF"): string {
  const decimals = getDecimalPlaces(currency);
  const amount = decimals === 0 ? cents : cents / 100;
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: currency.toUpperCase(),
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(amount);
}

/** Alias rétrocompatible — utilise la logique multi-devise. */
export function formatCents(cents: number, currency = "XAF"): string {
  return formatAmount(cents, currency);
}

export function centsToDecimal(cents: number, currency = "XAF"): number {
  return getDecimalPlaces(currency) === 0 ? cents : cents / 100;
}

export function decimalToCents(amount: number, currency = "XAF"): number {
  return getDecimalPlaces(currency) === 0 ? Math.round(amount) : Math.round(amount * 100);
}

/** Liste des devises supportées par l'organisation. */
export const SUPPORTED_CURRENCIES = [
  { code: "XAF", label: "Franc CFA (XAF)" },
  { code: "EUR", label: "Euro (EUR)" },
  { code: "USD", label: "Dollar US (USD)" },
  { code: "GNF", label: "Franc guinéen (GNF)" },
  { code: "NGN", label: "Naira nigérian (NGN)" },
  { code: "GHS", label: "Cedi ghanéen (GHS)" },
  { code: "MAD", label: "Dirham marocain (MAD)" },
] as const;

export type SupportedCurrency = typeof SUPPORTED_CURRENCIES[number]["code"];
