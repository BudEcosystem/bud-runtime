/**
 * Extract a human-readable error message from various API error response formats.
 *
 * Handles:
 * - Pydantic validation errors (422): { detail: [{ msg: "..." }, ...] }
 * - FastAPI HTTPException: { detail: "string" }
 * - FastAPI HTTPException with object: { detail: { error: "...", message: "..." } }
 * - Validation errors with errors array: { detail: { errors: ["..."] } }
 * - Custom error format: { message: "..." } or { msg: "..." }
 * - Axios/network errors: error.message
 */
export const extractApiErrorMessage = (
  error: unknown,
  fallback: string
): string => {
  if (!error || typeof error !== "object") return fallback;

  const err = error as Record<string, any>;
  const responseData = err?.response?.data;
  const detail = responseData?.detail;

  // Handle Pydantic validation error array: { detail: [{ msg: "..." }, ...] }
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item: any) => item?.msg)
      .filter(Boolean)
      .map((msg: string) => msg.replace(/^Value error, /i, ""));
    if (messages.length > 0) {
      return messages.join(". ");
    }
  }

  // Handle detail.errors array: { detail: { errors: ["...", "..."] } }
  if (detail?.errors && Array.isArray(detail.errors) && detail.errors.length > 0) {
    return detail.errors.join(". ");
  }

  // Handle detail.error string: { detail: { error: "..." } }
  if (detail?.error && typeof detail.error === "string") {
    return detail.error;
  }

  // Handle detail.message: { detail: { message: "..." } }
  if (detail?.message && typeof detail.message === "string") {
    return detail.message;
  }

  // Handle detail as string: { detail: "..." }
  if (typeof detail === "string") {
    return detail;
  }

  // Handle top-level message: { message: "..." }
  if (responseData?.message && typeof responseData.message === "string") {
    return responseData.message;
  }

  // Handle top-level msg: { msg: "..." }
  if (responseData?.msg && typeof responseData.msg === "string") {
    return responseData.msg;
  }

  // Handle axios/network error
  if (err?.message && typeof err.message === "string") {
    return err.message;
  }

  return fallback;
};
