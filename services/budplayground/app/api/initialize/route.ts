import { NextRequest, NextResponse } from 'next/server';
import axios from 'axios';
import { tempApiBaseUrl } from '@/app/lib/environment';

export async function POST(req: NextRequest) {
  try {
    const { jwt_token } = await req.json();

    if (!jwt_token) {
      return NextResponse.json(
        {
          error: 'JWT token is required',
          initialization_status: 'failed'
        },
        { status: 400 }
      );
    }

    // Use tempApiBaseUrl or fallback to localhost
    const apiBaseUrl = tempApiBaseUrl || 'http://localhost:8000';

    // Call budapp /playground/initialize endpoint
    const response = await axios.post(
      `${apiBaseUrl}/playground/initialize`,
      { jwt_token },
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${jwt_token}`,
        },
      }
    );

    // Return the initialization response
    return NextResponse.json(response.data);
  } catch (error: any) {
    console.error('Failed to initialize playground session:', error.response?.data || error.message);

    if (error.response) {
      // Check for specific error codes
      if (error.response.status === 401) {
        // JWT validation failed
        return NextResponse.json(
          {
            error: 'JWT validation failed. Token may be expired or invalid.',
            initialization_status: 'failed',
            code: error.response.data?.code || 401,
            message: error.response.data?.message || 'Unauthorized'
          },
          { status: 401 }
        );
      }

      // Forward the error response from budapp
      return NextResponse.json(
        {
          ...error.response.data,
          initialization_status: 'failed'
        },
        { status: error.response.status }
      );
    }

    // Generic error response
    return NextResponse.json(
      {
        error: 'Failed to initialize playground session',
        initialization_status: 'failed',
        message: error.message || 'Unknown error'
      },
      { status: 500 }
    );
  }
}
