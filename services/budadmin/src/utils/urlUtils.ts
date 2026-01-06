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

/**
 * Removes the 'prompt' and 'connector' parameters from the current URL
 * Used when closing agent/prompt editors to clean up the URL
 */
export function removePromptFromUrl(): void {
  if (typeof window === 'undefined') return;

  const params = new URLSearchParams(window.location.search);
  const newUrl = buildUrlWithParams(params, ['prompt', 'connector']);

  window.history.replaceState(
    { ...window.history.state },
    '',
    newUrl
  );
}

/**
 * Parses the connector URL parameter into an array of connector IDs
 * Format: "connA,connB,connC" -> ["connA", "connB", "connC"]
 * Positional: index maps to session index in the active sessions array
 * @param param - The connector URL parameter value
 * @returns An array of connector IDs (empty strings for positions without connectors)
 */
export function parseConnectorParam(param: string): string[] {
  if (!param) return [];
  return param.split(',');
}

/** Parameters that should not be URL-encoded (contain special chars like commas) */
const UNENCODED_PARAMS = ['agent', 'prompt', 'connector'];

/**
 * Builds a URL string from URLSearchParams with custom encoding rules
 * Certain parameters (agent, prompt, connector) are not encoded to preserve readability
 * @param params - The URLSearchParams to build from
 * @param excludeKeys - Keys to exclude from the final URL
 * @param additionalParams - Additional key-value pairs to add (not encoded)
 * @returns The built URL string
 */
function buildUrlWithParams(
  params: URLSearchParams,
  excludeKeys: string[] = [],
  additionalParams: Record<string, string> = {}
): string {
  const queryParts: string[] = [];

  params.forEach((value, key) => {
    if (!excludeKeys.includes(key) && value) {
      if (UNENCODED_PARAMS.includes(key)) {
        queryParts.push(`${key}=${value}`);
      } else {
        queryParts.push(`${key}=${encodeURIComponent(value)}`);
      }
    }
  });

  // Add additional params without encoding
  Object.entries(additionalParams).forEach(([key, value]) => {
    if (value) {
      queryParts.push(`${key}=${value}`);
    }
  });

  return queryParts.length > 0
    ? `${window.location.pathname}?${queryParts.join('&')}`
    : window.location.pathname;
}

/**
 * Builds a connector URL parameter string from an array
 * @param connectors - Array of connector IDs (empty strings for positions without connectors)
 * @returns The connector parameter string
 */
export function buildConnectorParam(connectors: string[]): string {
  // Trim trailing empty strings
  let lastNonEmpty = connectors.length - 1;
  while (lastNonEmpty >= 0 && !connectors[lastNonEmpty]) {
    lastNonEmpty--;
  }
  if (lastNonEmpty < 0) return '';
  return connectors.slice(0, lastNonEmpty + 1).join(',');
}

/**
 * Updates the connector for a specific position in the URL
 * @param position - The session index (position) to update
 * @param connectorId - The connector ID to set, or null/empty to clear
 * @param totalPositions - Total number of active sessions
 */
export function updateConnectorInUrl(position: number, connectorId: string | null, totalPositions: number): void {
  if (typeof window === 'undefined' || position < 0) return;

  const params = new URLSearchParams(window.location.search);
  const currentParam = params.get('connector') || '';
  const connectors = parseConnectorParam(currentParam);

  // Ensure array is large enough
  while (connectors.length < totalPositions) {
    connectors.push('');
  }

  // Update the position
  connectors[position] = connectorId || '';

  const newParam = buildConnectorParam(connectors);

  // Skip if nothing changed
  if (newParam === currentParam) return;

  const additionalParams = newParam ? { connector: newParam } : {};
  const newUrl = buildUrlWithParams(params, ['connector'], additionalParams);

  // Only update if URL actually changed
  if (newUrl !== window.location.pathname + window.location.search) {
    window.history.pushState({}, '', newUrl);
  }
}

/**
 * Gets the connector ID for a specific position from the URL
 * @param position - The session index (position) to get connector for
 * @returns The connector ID or null if not found/empty
 */
export function getConnectorFromUrlByPosition(position: number): string | null {
  if (typeof window === 'undefined' || position < 0) return null;

  const params = new URLSearchParams(window.location.search);
  const connectorParam = params.get('connector') || '';
  const connectors = parseConnectorParam(connectorParam);
  const connectorId = connectors[position];
  return connectorId && connectorId.length > 0 ? connectorId : null;
}

/**
 * Cleans up connector array to match the number of active sessions
 * @param totalSessions - Total number of active sessions to keep
 */
export function cleanupConnectorParams(totalSessions: number): void {
  if (typeof window === 'undefined') return;

  const params = new URLSearchParams(window.location.search);
  const currentParam = params.get('connector') || '';

  if (!currentParam) return;

  const connectors = parseConnectorParam(currentParam);

  // Only keep connectors up to the number of sessions
  const trimmedConnectors = connectors.slice(0, totalSessions);

  const newParam = buildConnectorParam(trimmedConnectors);

  // Only update URL if the param actually changed
  if (newParam === currentParam) return;

  const additionalParams = newParam ? { connector: newParam } : {};
  const newUrl = buildUrlWithParams(params, ['connector'], additionalParams);

  // Only update if URL actually changed
  if (newUrl !== window.location.pathname + window.location.search) {
    window.history.replaceState(
      { ...window.history.state },
      '',
      newUrl
    );
  }
}
