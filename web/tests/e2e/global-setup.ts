import { execFileSync } from "node:child_process";
import path from "node:path";

export default async function globalSetup() {
  const repoRoot = path.resolve(__dirname, "../../..");
  const webRoot = path.join(repoRoot, "web");

  if (process.env.PLAYWRIGHT_SKIP_BROWSER_INSTALL !== "1") {
    execFileSync("npx", ["playwright", "install", "chromium"], {
      cwd: webRoot,
      stdio: "inherit",
      env: process.env,
    });
  }

  if (process.env.SMOKE_REUSE_EXISTING_STACK === "1") {
    return;
  }

  process.env.PHASE4_E2E_PROVIDER ||= "local";
  process.env.STEPFUN_API_KEY ||= "phase4-local-e2e";

  execFileSync("bash", [path.join(repoRoot, "scripts", "dev-smoke-up.sh")], {
    cwd: repoRoot,
    stdio: "inherit",
    env: process.env,
  });
}
