import { spawnSync } from "node:child_process";

const BLOCKED_PATH_SEGMENTS = new Set([
  "node_modules",
  ".next",
  "dist",
  "coverage",
]);

function normalizeVitestArg(arg) {
  if (typeof arg !== "string" || arg.startsWith("-")) {
    return arg;
  }

  return arg.replace(/^\.\/web\//, "").replace(/^web\//, "");
}

function assertProjectScopedArg(arg) {
  if (typeof arg !== "string" || arg.startsWith("-")) {
    return;
  }

  const pathSegments = arg.split(/[\\/]+/).filter(Boolean);
  const blockedSegment = pathSegments.find((segment) =>
    BLOCKED_PATH_SEGMENTS.has(segment),
  );

  if (blockedSegment) {
    throw new Error(
      `Refusing to run Vitest against ${blockedSegment}; root npm test is scoped to web project tests.`,
    );
  }
}

const normalizedArgs = process.argv.slice(2).map((arg) =>
  normalizeVitestArg(arg),
);

normalizedArgs.forEach(assertProjectScopedArg);

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
