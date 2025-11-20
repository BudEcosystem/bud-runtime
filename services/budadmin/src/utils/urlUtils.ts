/**
 * Updates URL query parameters and optionally updates browser history
 * @param params - Object with key-value pairs to set or null to delete
 * @param options - Configuration options
 * @returns The new URL string
 */
export function updateQueryParams(
  params: Record<string, string | null>,
  options: {
    /** Whether to replace browser history state (default: false) */
    replaceHistory?: boolean;
    /** Base path to use (default: window.location.pathname) */
    basePath?: string;
    /** Base search params to start with (default: window.location.search) */
    baseSearch?: string;
  } = {}
): string {
  const { replaceHistory = false, basePath, baseSearch } = options;

  const currentPath = basePath ?? window.location.pathname;
  const urlParams = new URLSearchParams(baseSearch ?? window.location.search);

  // Update or delete parameters
  Object.entries(params).forEach(([key, value]) => {
    if (value === null) {
      urlParams.delete(key);
    } else {
      urlParams.set(key, value);
    }
  });

  // Build the new URL
  const queryString = urlParams.toString();
  const newUrl = queryString ? `${currentPath}?${queryString}` : currentPath;

  // Update browser history if requested
  if (replaceHistory) {
    window.history.replaceState(
      { ...window.history.state },
      '',
      newUrl
    );
  }

  return newUrl;
}
