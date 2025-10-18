import { tempApiBaseUrl } from '@/app/lib/environment';
import axios from 'axios';
import { NextResponse } from 'next/server';

export async function GET(
  req: Request,
  { params }: { params: { prompt_id: string } }
) {
  const { prompt_id } = params;

  // Get the JWT token from Authorization header (case-insensitive)
  const authHeader = req.headers.get('authorization') || req.headers.get('Authorization');
  const apiKey = req.headers.get('api-key');

  // Build headers object conditionally
  const headers: any = {
    'Content-Type': 'application/json',
  };

  if (authHeader) {
    headers['Authorization'] = authHeader;
  }

  if (apiKey) {
    headers['api-key'] = apiKey;
  }

  try {
    const result = await axios
      .get(`${tempApiBaseUrl}/prompts/prompt-config/${prompt_id}`, {
        headers,
      })
      .then((response) => {
        return response.data;
      });
    return NextResponse.json(result);
  } catch (error: any) {
    // Return the actual error from the backend
    if (error.response?.data) {
      return NextResponse.json(error.response.data, { status: error.response.status });
    }
    return NextResponse.json({
      error: 'Failed to fetch prompt configuration',
      message: error.message || 'Unknown error',
      status: error.status || 500
    }, { status: error.status || 500 });
  }
}
