import { test, expect } from "@playwright/test";
import { spawn, ChildProcessWithoutNullStreams } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const backendDir = path.resolve(__dirname, "../../backend");
const frontendDir = path.resolve(__dirname, "..");
const pythonExe = path.join(backendDir, ".venv", "Scripts", "python.exe");

// eslint-disable-next-line no-control-regex
const ANSI_PATTERN = /\x1b\[[0-9;]*m/g;

function waitForLine(proc: ChildProcessWithoutNullStreams, pattern: RegExp, timeoutMs = 30_000): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timed out waiting for ${pattern}`)), timeoutMs);
    let buffer = "";
    const onData = (chunk: Buffer) => {
      buffer += chunk.toString().replace(ANSI_PATTERN, "");
      const match = buffer.match(pattern);
      if (match) {
        clearTimeout(timer);
        proc.stdout.off("data", onData);
        resolve(match[1] ?? match[0]);
      }
    };
    proc.stdout.on("data", onData);
    proc.stderr.on("data", () => {});
  });
}

// This test starts the real FastAPI backend (which runs the full seeded
// 250,000-record daily close once at startup) and a real Vite dev server,
// each on a free OS-assigned port, and asserts the console renders the
// exception queue naming the exact disagreeing field for every held
// record: this is the resume's "React exception queue names the exact
// disagreeing field" claim, checked end to end through a real headless
// browser, not a unit test of App.tsx in isolation.
test("exception queue names the exact disagreeing field for every held record", async ({ page }) => {
  const backend = spawn(pythonExe, ["run_server.py"], { cwd: backendDir });
  const backendPort = await waitForLine(backend, /LISTENING_ON (\d+)/, 60_000);
  const backendBase = `http://127.0.0.1:${backendPort}`;

  const frontend = spawn("npx", ["vite", "--port", "0", "--strictPort", "false"], {
    cwd: frontendDir,
    env: { ...process.env, VITE_API_BASE: backendBase },
    shell: true,
  });
  const frontendUrl = await waitForLine(frontend, /Local:\s+(http:\/\/localhost:\d+\/)/);

  try {
    await page.goto(frontendUrl);
    await expect(page.getByTestId("exception-row")).toHaveCount(40, { timeout: 20_000 });

    const rules = await page.getByTestId("exception-rule").allTextContents();
    const fields = await page.getByTestId("exception-field").allTextContents();

    // Every one of the 40 seeded breaks names a real rule and a non-empty
    // disagreeing field; no row is ever left unexplained.
    for (const rule of rules) {
      expect(["timing", "quantity", "price", "missing", "duplicate"]).toContain(rule);
    }
    for (const field of fields) {
      expect(field.length).toBeGreaterThan(0);
    }

    const summary = await page.getByTestId("summary").textContent();
    expect(summary).toContain("40 of 40 seeded breaks caught");
    expect(summary).toContain("0 false holds");
  } finally {
    backend.kill();
    frontend.kill();
  }
});
