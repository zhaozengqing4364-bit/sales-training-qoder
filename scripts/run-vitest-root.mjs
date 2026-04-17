import { spawnSync } from "node:child_process";

const normalizedArgs = process.argv.slice(2).map((arg) =>
  typeof arg === "string" ? arg.replace(/^web\//, "") : arg,
);
const hasExplicitProjectPath = normalizedArgs.some(
  (arg) => typeof arg === "string" && !arg.startsWith("-"),
);
const vitestArgs = hasExplicitProjectPath ? normalizedArgs : ["src", ...normalizedArgs];

const result = spawnSync(
  "pnpm",
  ["--dir", "web", "exec", "vitest", "run", ...vitestArgs],
  {
    stdio: "inherit",
    env: process.env,
  },
);

if (result.error) {
  throw result.error;
}

process.exit(result.status ?? 1);
