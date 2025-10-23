import axios from 'axios';
import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const body = await req.json();

  // Get the JWT token from Authorization header (case-insensitive)
  const authHeader = req.headers.get('authorization') || req.headers.get('Authorization');
  const apiKey = req.headers.get('api-key');
  const accessKey = req.headers.get('access-key');

  // Build headers object conditionally
  const headers: any = {
    'Content-Type': 'application/json',
  };

  if (authHeader) {
    headers['Authorization'] = authHeader;
  }

  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  if (accessKey) {
    headers['X-Access-Key'] = accessKey;
  }

  try {
    const result = await axios
      .post('http://gateway.dev.bud.studio/v1/responses', body, {
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
      error: 'Failed to submit prompt response',
      message: error.message || 'Unknown error',
      status: error.status || 500
    }, { status: error.status || 500 });
  }
}
