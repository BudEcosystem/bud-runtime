import { NextResponse } from 'next/server';

export async function GET() {
  // Server-side environment variables are always available at runtime
  const assetApiBaseUrl = process.env.NEXT_PUBLIC_TEMP_API_ASSET_URL || process.env.TEMP_API_ASSET_URL || '';

  return NextResponse.json({
    assetBaseUrl: assetApiBaseUrl ? `${assetApiBaseUrl}/static/` : '/static/',
  });
}
