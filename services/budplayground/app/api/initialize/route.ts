import { NextRequest, NextResponse } from 'next/server';
import axios from 'axios';
import { tempApiBaseUrl } from '@/app/lib/environment';

export async function POST(req: NextRequest) {
  try {
    const { refresh_token } = await req.json();

    if (!refresh_token) {
      return NextResponse.json(
        {
          error: 'Refresh token is required',
          initialization_status: 'failed'
        },
        { status: 400 }
      );
    }

    // Use tempApiBaseUrl or fallback to localhost
    const apiBaseUrl = tempApiBaseUrl || 'http://localhost:8000';

    // Call budapp /playground/initialize endpoint with refresh token
    const response = await axios.post(
      `${apiBaseUrl}/playground/initialize`,
      { refresh_token },
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    // Store tokens and session info with TTL for automatic refresh
    const initData = response.data;
    if (initData.initialization_status === 'success') {
      // Calculate when to refresh (90% of TTL to be safe)
      const refreshTime = initData.ttl ? Math.floor(initData.ttl * 0.9 * 1000) : null;

      return NextResponse.json({
        ...initData,
        refresh_time: refreshTime, // Time in milliseconds until refresh needed
        initialized_at: Date.now() // Timestamp when initialization happened
      });
    }

    // Return the initialization response
    return NextResponse.json(response.data);
  } catch (error: any) {
    console.error('Failed to initialize playground session:', error.response?.data || error.message);

    if (error.response) {
      // Check for specific error codes
      if (error.response.status === 401) {
        // Refresh token validation failed
        return NextResponse.json(
          {
            error: 'Refresh token validation failed. Token may be expired or invalid.',
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
