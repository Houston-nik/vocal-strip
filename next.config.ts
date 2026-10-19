import type { NextConfig } from "next";

const engine = process.env.ENGINE_URL ?? "http://127.0.0.1:8766";

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    "127.0.0.1",
    "localhost",
    "*.trycloudflare.com",
  ],
  experimental: {
    proxyClientMaxBodySize: "80mb",
  },
  async rewrites() {
    return [
      {
        source: "/engine/:path*",
        destination: `${engine}/:path*`,
      },
    ];
  },
};

export default nextConfig;
