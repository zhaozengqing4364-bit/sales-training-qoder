import { execFileSync } from "node:child_process";
import path from "node:path";

export default async function globalTeardown() {
  const repoRoot = path.resolve(__dirname, "../../..");

  if (process.env.SMOKE_REUSE_EXISTING_STACK === "1") {
    return;
  }

  execFileSync("bash", [path.join(repoRoot, "scripts", "dev-smoke-stop.sh")], {
    cwd: repoRoot,
    stdio: "inherit",
    env: process.env,
  });
}
