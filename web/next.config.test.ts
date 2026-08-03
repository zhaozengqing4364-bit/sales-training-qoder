import { describe, expect, it } from "vitest";

import { isCsrfOriginAllowed } from "next/dist/server/app-render/csrf-protection";

import nextConfig from "./next.config";

describe("next dev config", () => {
  it("keeps proxied material uploads above the backend file-size ceiling", () => {
    expect(nextConfig.experimental?.proxyClientMaxBodySize).toBe("310mb");
  });

  it("proxies same-origin browser API requests to the internal backend", async () => {
    const rewrites = await nextConfig.rewrites?.();

    expect(rewrites).toEqual(
      expect.arrayContaining([
        {
          source: "/api/v1/:path*",
          destination: "http://127.0.0.1:3444/api/v1/:path*",
        },
        {
          source: "/health",
          destination: "http://127.0.0.1:3444/health",
        },
        {
          source: "/ws/:path*",
          destination: "http://127.0.0.1:3444/ws/:path*",
        },
      ]),
    );
  });

  it("allows HMR access from any IPv4 browser host in shared dev sessions", () => {
    expect(
      isCsrfOriginAllowed("203.0.113.42", nextConfig.allowedDevOrigins),
    ).toBe(true);
  });

  it("keeps Turbopack and output tracing inside the frontend package", () => {
    expect(nextConfig.turbopack?.root).toBe(process.cwd());
    expect(nextConfig.outputFileTracingRoot).toBe(process.cwd());
  });
});
