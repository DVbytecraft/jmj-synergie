export function formatDateFr(dateInput: string | number | Date): string {
  const d = dateInput instanceof Date ? dateInput : new Date(dateInput);

  // Guard against invalid dates
  if (Number.isNaN(d.getTime())) return "";

  // Deterministic formatting (UTC) to avoid SSR/client locale+timezone mismatches
  const year = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");

  return `${day}/${month}/${year}`;
}

export function formatDateTimeFr(dateInput: string | number | Date): string {
  const d = dateInput instanceof Date ? dateInput : new Date(dateInput);
  if (Number.isNaN(d.getTime())) return "";

  const year = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  const hours = String(d.getUTCHours()).padStart(2, "0");
  const minutes = String(d.getUTCMinutes()).padStart(2, "0");

  return `${day}/${month}/${year} ${hours}:${minutes}`;
}

