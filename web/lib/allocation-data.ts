import "server-only";
import { promises as fs } from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { isAllocationResearch, type AllocationResearch } from "./allocation-types";
export async function loadAllocationResearch(): Promise<{data: AllocationResearch | null; error: string | null}> {
  try {
    const folder = path.join(process.cwd(), "data");
    const [raw, expected] = await Promise.all([fs.readFile(path.join(folder, "allocation-research.json"), "utf8"), fs.readFile(path.join(folder, "allocation-research.sha256"), "utf8")]);
    if (createHash("sha256").update(raw).digest("hex") !== expected.trim()) throw new Error("Hash mismatch");
    const data: unknown = JSON.parse(raw);
    if (!isAllocationResearch(data)) throw new Error("Invalid contract");
    return {data, error: null};
  } catch (error) {
    const missing = (error as NodeJS.ErrnoException).code === "ENOENT";
    return {data: null, error: missing ? "No approved research export is available yet." : "Research data could not be verified. Regenerate the approved export before using these results."};
  }
}
