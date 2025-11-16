/**
 * Structured logging utility for better debugging
 */

export interface LogContext {
  endpoint?: string;
  requestId?: string;
  method?: string;
  timestamp?: string;
  [key: string]: any;
}

export class Logger {
  private context: LogContext;
  private isDevelopment: boolean;

  constructor(context: LogContext = {}) {
    this.context = {
      timestamp: new Date().toISOString(),
      ...context,
    };
    this.isDevelopment = process.env.NODE_ENV === 'development';
  }

  private formatMessage(level: string, message: string, data?: any): string {
    const prefix = `[${this.context.endpoint || 'API'}]`;
    const timestamp = `[${this.context.timestamp}]`;
    return `${timestamp} ${prefix} ${level}: ${message}`;
  }

  private sanitizeHeaders(headers: Record<string, string>): Record<string, string> {
    const sanitized = { ...headers };
    const sensitiveKeys = ['authorization', 'api-key', 'cookie', 'set-cookie'];

    // HTTP headers are case-insensitive, so check case-insensitively
    for (const key in sanitized) {
      if (sensitiveKeys.includes(key.toLowerCase())) {
        if (sanitized[key]) {
          // Show only first 10 chars for debugging
          sanitized[key] = sanitized[key].substring(0, 10) + '...[REDACTED]';
        }
      }
    }

    return sanitized;
  }

  info(message: string, data?: any) {
    console.log(this.formatMessage('INFO', message));
    if (data && this.isDevelopment) {
      console.log('Data:', JSON.stringify(data, null, 2));
    }
  }

  warn(message: string, data?: any) {
    console.warn(this.formatMessage('WARN', message));
    if (data) {
      console.warn('Data:', JSON.stringify(data, null, 2));
    }
  }

  error(message: string, error?: any, additionalContext?: any) {
    console.error(this.formatMessage('ERROR', message));

    if (error) {
      // Log error details
      if (error instanceof Error) {
        console.error('Error Message:', error.message);
        if (this.isDevelopment && error.stack) {
          console.error('Stack Trace:', error.stack);
        }
      } else if (typeof error === 'object') {
        console.error('Error Details:', JSON.stringify(error, null, 2));
      } else {
        console.error('Error:', error);
      }
    }

    if (additionalContext) {
      console.error('Additional Context:', JSON.stringify(additionalContext, null, 2));
    }
  }

  logRequest(body: any, headers: Record<string, string>) {
    if (!this.isDevelopment) return;

    this.info('Incoming Request');
    console.log('Headers:', JSON.stringify(this.sanitizeHeaders(headers), null, 2));
    console.log('Body:', JSON.stringify(body, null, 2));
  }

  logResponse(status: number, body?: any) {
    if (!this.isDevelopment) return;

    this.info(`Response Status: ${status}`);
    if (body) {
      console.log('Response Body:', typeof body === 'string' ? body.substring(0, 200) : JSON.stringify(body, null, 2));
    }
  }

  logGatewayRequest(url: string, method: string, headers: Record<string, string>, body: any) {
    this.info(`Gateway Request: ${method} ${url}`);
    if (this.isDevelopment) {
      console.log('Gateway Headers:', JSON.stringify(this.sanitizeHeaders(headers), null, 2));
      console.log('Gateway Body:', JSON.stringify(body, null, 2));
    }
  }

  logGatewayResponse(status: number, body: string) {
    this.info(`Gateway Response: ${status}`);
    if (this.isDevelopment) {
      console.log('Gateway Response Body:', body.substring(0, 500));
    }
  }
}

/**
 * Extract user-friendly error message from various error formats
 */
export function extractErrorMessage(error: any): string {
  // Handle different error formats from the gateway/backend

  // Case 1: Error is already a string
  if (typeof error === 'string') {
    return error;
  }

  // Case 2: Error has a message property (object with nested message)
  if (error?.error?.message && typeof error.error.message === 'string') {
    return error.error.message;
  }

  // Case 3: Error is an object with message at root level
  if (error?.message && typeof error.message === 'string') {
    return error.message;
  }

  // Case 4: Error is an object with error property that's a string
  if (error?.error && typeof error.error === 'string') {
    return error.error;
  }

  // Case 5: Error has a detail field (FastAPI format)
  if (error?.detail && typeof error.detail === 'string') {
    return error.detail;
  }

  // Case 6: Error is an array of details (validation errors)
  if (Array.isArray(error?.detail)) {
    return error.detail.map((d: any) => d.msg || d.message).join(', ');
  }

  // Fallback
  return 'An unexpected error occurred';
}

/**
 * Categorize error and provide user-friendly message
 */
export function categorizeError(statusCode: number, errorMessage: string): {
  category: string;
  userMessage: string;
  technicalMessage: string;
} {
  const lowerMessage = errorMessage.toLowerCase();

  // Authentication errors
  if (statusCode === 401 || statusCode === 403 || lowerMessage.includes('unauthorized') || lowerMessage.includes('api key')) {
    return {
      category: 'authentication',
      userMessage: 'Authentication failed. Please check your API key or refresh your session.',
      technicalMessage: errorMessage,
    };
  }

  // Not found errors
  if (statusCode === 404 || lowerMessage.includes('not found')) {
    return {
      category: 'not_found',
      userMessage: 'The requested resource was not found. It may have been deleted or you don\'t have access.',
      technicalMessage: errorMessage,
    };
  }

  // Validation errors
  if (statusCode === 400 || statusCode === 422 || lowerMessage.includes('validation') || lowerMessage.includes('invalid')) {
    return {
      category: 'validation',
      userMessage: 'Invalid input. Please check your configuration and try again.',
      technicalMessage: errorMessage,
    };
  }

  // Server errors
  if (statusCode >= 500 || lowerMessage.includes('internal server') || lowerMessage.includes('gateway')) {
    return {
      category: 'server',
      userMessage: 'Service temporarily unavailable. Please try again in a moment.',
      technicalMessage: errorMessage,
    };
  }

  // Network/timeout errors
  if (lowerMessage.includes('timeout') || lowerMessage.includes('network') || lowerMessage.includes('connection')) {
    return {
      category: 'network',
      userMessage: 'Connection error. Please check your internet connection and try again.',
      technicalMessage: errorMessage,
    };
  }

  // Generic error
  return {
    category: 'unknown',
    userMessage: 'An error occurred while processing your request. Please try again.',
    technicalMessage: errorMessage,
  };
}
