import { tempApiBaseUrl } from '@/app/lib/environment';
import { Logger, extractErrorMessage, categorizeError } from '@/app/lib/logger';
import { parsePositiveIntParam } from '@/app/lib/query';
import axios from 'axios';
import { NextResponse } from 'next/server';

export async function GET(
  req: Request,
  { params }: { params: Promise<{ prompt_id: string }> }
) {
  const { prompt_id } = await params;
  const logger = new Logger({ endpoint: 'Prompt Fetch', method: 'GET', promptId: prompt_id });

  // Get the JWT token from Authorization header (case-insensitive)
  const authHeader = req.headers.get('authorization') || req.headers.get('Authorization');
  const apiKey = req.headers.get('api-key');

  logger.info(`Fetching prompt configuration for: ${prompt_id}`);

  // Build headers object conditionally
  const headers: any = {
    'Content-Type': 'application/json',
  };

  if (authHeader) {
    headers['Authorization'] = authHeader;
  } else {
    logger.warn('No Authorization header present');
  }

  if (apiKey) {
    headers['api-key'] = apiKey;
  } else {
    logger.warn('No API key present');
  }

  // Log sanitized headers
  const requestUrl = new URL(req.url);
  const versionParam = parsePositiveIntParam(requestUrl.searchParams.get('version'));
  logger.logRequest({ prompt_id, ...(versionParam ? { version: versionParam } : {}) }, headers);

  const versionQuery = versionParam ? `?version=${encodeURIComponent(versionParam)}` : '';
  const backendUrl = `${tempApiBaseUrl}/prompts/prompt-config/${prompt_id}${versionQuery}`;
  logger.info(`Backend URL: ${backendUrl}`);

  try {
    const result = await axios
      .get(backendUrl, { headers })
      .then((response) => {
        logger.info(`Successfully fetched prompt configuration, status: ${response.status}`);
        return response.data;
      });
    return NextResponse.json(result);
  } catch (error: any) {
    // Log detailed error information
    logger.error('Failed to fetch prompt configuration', error, {
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      url: backendUrl,
    });

    // Return the actual error from the backend
    if (error.response?.data) {
      const statusCode = error.response.status;
      const errorData = error.response.data;

      // Extract and categorize the error
      const errorMessage = extractErrorMessage(errorData);
      const categorized = categorizeError(statusCode, errorMessage);

      logger.error('Returning error to client', {
        statusCode,
        userMessage: categorized.userMessage,
        technicalMessage: categorized.technicalMessage,
      });

      return NextResponse.json({
        error: categorized.userMessage,
        details: process.env.NODE_ENV === 'development' ? categorized.technicalMessage : undefined,
        originalError: process.env.NODE_ENV === 'development' ? errorData : undefined,
      }, { status: statusCode });
    }

    // Generic error fallback
    // For axios errors, status is at error.response.status
    const statusCode = error.response?.status || error.status || 500;
    const errorMessage = error.message || 'Unknown error';
    const categorized = categorizeError(statusCode, errorMessage);

    logger.error('Returning generic error to client', {
      statusCode,
      errorMessage,
    });

    return NextResponse.json({
      error: categorized.userMessage,
      details: process.env.NODE_ENV === 'development' ? errorMessage : undefined,
    }, { status: statusCode });
  }
}
