import { describe, expect, it } from "vitest";

import { isCsrfOriginAllowed } from "next/dist/server/app-render/csrf-protection";

import nextConfig from "./next.config";

describe("next dev config", () => {
  it("allows HMR access from any IPv4 browser host in shared dev sessions", () => {
    expect(
      isCsrfOriginAllowed("203.0.113.42", nextConfig.allowedDevOrigins),
    ).toBe(true);
  });
});
