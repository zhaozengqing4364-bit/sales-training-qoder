import type { NextConfig } from "next";

const frontendRoot = process.cwd();
const internalApiBaseUrl = (
  process.env.SERVER_API_URL || "http://127.0.0.1:3444/api/v1"
).replace(/\/+$/, "");
const internalBackendBaseUrl = internalApiBaseUrl.replace(/\/api\/v1$/, "");

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next",
  allowedDevOrigins: ["127.0.0.1", "*.*.*.*"],
  outputFileTracingRoot: frontendRoot,
  reactCompiler: true,
  experimental: {
    // Material files are capped at 300 MB by the backend. Next rewrites clone
    // multipart bodies, so the proxy needs a small allowance for form metadata.
    proxyClientMaxBodySize: "310mb",
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${internalApiBaseUrl}/:path*`,
      },
      {
        source: "/health",
        destination: `${internalBackendBaseUrl}/health`,
      },
      {
        source: "/ws/:path*",
        destination: `${internalBackendBaseUrl}/ws/:path*`,
      },
    ];
  },
  turbopack: {
    root: frontendRoot,
  },
};

export default nextConfig;
