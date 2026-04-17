import { spawnSync } from "node:child_process";

const result = spawnSync("pnpm", ["--dir", "web", "exec", "vitest", "--list"], {
  encoding: "utf8",
  env: process.env,
});

const output = `${result.stdout || ""}${result.stderr || ""}`;

if (result.error) {
  throw result.error;
}

if (output.includes("node_modules/") || output.includes("node_modules\\")) {
  console.error(output);
  throw new Error("Vitest discovery included node_modules tests.");
}

if (result.status !== 0) {
  console.error(output);
  process.exit(result.status ?? 1);
}

console.log("Vitest discovery scoped to project tests (no node_modules entries).");
