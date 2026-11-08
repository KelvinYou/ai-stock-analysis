import "server-only";
import { promises as fs } from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { isMomentumDashboard, momentumDashboardForDate, type MomentumDashboard } from "./momentum-types";

const PUBLIC_SNAPSHOT = "https://raw.githubusercontent.com/KelvinYou/ai-stock-analysis/main/web/data/momentum.json";

export async function loadMomentumDashboard(): Promise<{data: MomentumDashboard | null; error: string | null}> {
  try {
    const source = process.env.MOMENTUM_SNAPSHOT_URL || (process.env.NODE_ENV === "production" ? PUBLIC_SNAPSHOT : "");
    let raw: string, expected: string;
    if (source) {
      const url = new URL(source);
      if (url.protocol !== "https:" || url.username || url.password || !url.pathname.endsWith(".json")) throw new Error("Invalid source");
      const responses = await Promise.all([source, source.replace(/\.json$/, ".sha256")].map(address =>
        fetch(address, {next: {revalidate: 60}, signal: AbortSignal.timeout(10000)})));
      if (responses.some(response => !response.ok)) throw new Error("Source unavailable");
      [raw, expected] = await Promise.all(responses.map(response => response.text()));
    } else {
      [raw, expected] = await Promise.all(["momentum.json", "momentum.sha256"].map(name =>
        fs.readFile(path.join(process.cwd(), "data", name), "utf8")));
    }
    if (createHash("sha256").update(raw).digest("hex") !== expected.trim()) throw new Error("Hash mismatch");
    const data: unknown = JSON.parse(raw);
    if (!isMomentumDashboard(data)) throw new Error("Invalid snapshot");
    return {data: momentumDashboardForDate(data), error: null};
  } catch {
    return {data: null, error: "The momentum price snapshot could not be verified. Target weights are unavailable until the next successful refresh."};
  }
}
