import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactStrictMode: false,
  allowedDevOrigins: ['local-origin.dev', '*.local-origin.dev'],
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'newwavesolution.com',
        pathname: '/wp-content/**',
      },
      {
        protocol: 'https',
        hostname: 'encrypted-tbn0.gstatic.com',
        pathname: '/images/**',
      },
    ],
  },
};

export default nextConfig;
