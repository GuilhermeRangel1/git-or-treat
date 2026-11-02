/** Color follows the sign displayed to the user; zero has the theme's normal text color. */
export function signedValueTone(value: number | null, showPositiveSign = true) {
  if (value === null) return "text-muted";
  if (value < 0) return "text-danger";
  if (value > 0 && showPositiveSign) return "text-success";
  return "text-content";
}
