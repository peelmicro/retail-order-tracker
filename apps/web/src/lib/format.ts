/** Format an integer amount (minor units / cents) as a currency string.
 *
 * Example: formatMinorUnits(123450, "EUR") -> "€1,234.50"
 */
export function formatMinorUnits(minor: number, currency = "EUR"): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(minor / 100);
}

/** Format a number with thousands separator. */
export function formatCount(n: number): string {
  return new Intl.NumberFormat("en-GB").format(n);
}

/** Format an ISO date string (YYYY-MM-DD) for display. */
export function formatDate(isoDate: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(isoDate));
}
