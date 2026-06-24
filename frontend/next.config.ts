import type { NextConfig } from "next";

const apiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://backend:5001';

const nextConfig: NextConfig = {
  eslint: {
    // Don't fail builds on ESLint errors
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Don't fail builds on TypeScript errors
    ignoreBuildErrors: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
