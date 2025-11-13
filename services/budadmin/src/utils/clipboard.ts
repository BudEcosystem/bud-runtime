/**
 * Robust clipboard copy utility with HTTP fallback support.
 *
 * This utility provides a reliable way to copy text to the clipboard that works in both
 * HTTPS (modern clipboard API) and HTTP (fallback using document.execCommand) environments.
 *
 * @module clipboard
 */

export interface CopyToClipboardOptions {
  /** Optional callback when copy succeeds */
  onSuccess?: () => void;
  /** Optional callback when copy fails */
  onError?: (error: Error) => void;
  /** Enable console logging for debugging (default: true) */
  enableLogging?: boolean;
}

export interface CopyToClipboardResult {
  success: boolean;
  error?: Error;
  method?: 'clipboard-api' | 'fallback';
}

/**
 * Copies text to the clipboard with automatic fallback for HTTP environments.
 *
 * Features:
 * - Validates input text before attempting to copy
 * - Checks for Clipboard API availability (requires HTTPS or localhost)
 * - Falls back to document.execCommand for HTTP environments
 * - Comprehensive error handling and logging
 * - TypeScript support with return type
 *
 * @param text - The text to copy to clipboard
 * @param options - Optional configuration for callbacks and logging
 * @returns Promise resolving to result object with success status
 *
 * @example
 * ```typescript
 * // Basic usage
 * const result = await copyToClipboard("Hello World");
 * if (result.success) {
 *   console.log("Copied!");
 * }
 *
 * // With callbacks
 * await copyToClipboard("API Key: 12345", {
 *   onSuccess: () => setMessage("Copied to clipboard!"),
 *   onError: (err) => setMessage("Failed to copy")
 * });
 * ```
 */
export async function copyToClipboard(
  text: string,
  options: CopyToClipboardOptions = {}
): Promise<CopyToClipboardResult> {
  const { onSuccess, onError, enableLogging = true } = options;

  // Validate the text before attempting to copy
  if (!text || text === "Loading..." || text.trim() === "") {
    const error = new Error("Cannot copy: Invalid or empty text");
    if (enableLogging) {
      console.error(error.message);
    }
    if (onError) {
      onError(error);
    }
    return { success: false, error };
  }

  // Check if clipboard API is available (requires HTTPS or localhost)
  if (!navigator.clipboard) {
    if (enableLogging) {
      console.warn("Clipboard API not available (HTTP context), using fallback");
    }

    // Fallback for HTTP environments using document.execCommand
    try {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      textArea.style.top = "-999999px";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      const successful = document.execCommand("copy");
      document.body.removeChild(textArea);

      if (successful) {
        if (onSuccess) {
          onSuccess();
        }
        return { success: true, method: 'fallback' };
      } else {
        const error = new Error("Fallback copy failed: execCommand returned false");
        if (enableLogging) {
          console.error(error.message);
        }
        if (onError) {
          onError(error);
        }
        return { success: false, error, method: 'fallback' };
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error("Fallback copy error: " + String(err));
      if (enableLogging) {
        console.error("Fallback copy error:", error);
      }
      if (onError) {
        onError(error);
      }
      return { success: false, error, method: 'fallback' };
    }
  }

  // Modern clipboard API for HTTPS environments
  try {
    await navigator.clipboard.writeText(text);
    if (onSuccess) {
      onSuccess();
    }
    return { success: true, method: 'clipboard-api' };
  } catch (err) {
    const error = err instanceof Error ? err : new Error("Clipboard API error: " + String(err));
    if (enableLogging) {
      console.error("Clipboard API error:", error);
    }
    if (onError) {
      onError(error);
    }
    return { success: false, error, method: 'clipboard-api' };
  }
}

/**
 * Simple wrapper for copyToClipboard that returns only a boolean.
 * Useful when you don't need detailed error information.
 *
 * @param text - The text to copy to clipboard
 * @returns Promise resolving to true if successful, false otherwise
 *
 * @example
 * ```typescript
 * const success = await simpleCopy("Hello World");
 * setMessage(success ? "Copied!" : "Failed to copy");
 * ```
 */
export async function simpleCopy(text: string): Promise<boolean> {
  const result = await copyToClipboard(text, { enableLogging: false });
  return result.success;
}
