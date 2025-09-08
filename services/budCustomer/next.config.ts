import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: false,
  experimental: {
    // Ensure consistent CSS class generation
    esmExternals: 'loose',
  },
  webpack: (config) => {
    // Ignore the optional memcpy module that bytebuffer tries to load
    config.resolve.fallback = {
      ...config.resolve.fallback,
      memcpy: false,
    };
    return config;
  },
  onDemandEntries: {
    maxInactiveAge: 60 * 60 * 1000,
    pagesBufferLength: 5,
  },
};

export default nextConfig;
