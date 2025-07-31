import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: '/auth/login',
        destination: '/login',
        permanent: true,
      },
      {
        source: '/auth/register',
        destination: '/register', 
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
