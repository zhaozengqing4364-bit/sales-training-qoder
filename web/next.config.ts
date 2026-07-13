import type { NextConfig } from "next";

const frontendRoot = process.cwd();

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "*.*.*.*"],
  outputFileTracingRoot: frontendRoot,
  reactCompiler: true,
  turbopack: {
    root: frontendRoot,
  },
};

export default nextConfig;
