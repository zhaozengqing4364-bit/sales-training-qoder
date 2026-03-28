import { spawnSync } from "node:child_process";

const normalizedArgs = process.argv.slice(2).map((arg) =>
  typeof arg === "string" ? arg.replace(/^web\//, "") : arg,
);

const result = spawnSync(
  "pnpm",
  ["--dir", "web", "exec", "vitest", "run", ...normalizedArgs],
  {
    stdio: "inherit",
    env: process.env,
  },
);

if (result.error) {
  throw result.error;
}

process.exit(result.status ?? 1);
