import { loadAllocationResearch } from "@/lib/allocation-data";
export async function GET(request: Request) {
  const {data} = await loadAllocationResearch();
  if (!data) return Response.json({error: "Research export unavailable"}, {status: 503});
  const id = new URL(request.url).searchParams.get("id");
  const experiment = data.experiments.find(e => e.id === id);
  if (!experiment) return Response.json({error: "Unknown experiment"}, {status: 404});
  return Response.json({version: data.version, generated_at_utc: data.generated_at_utc, promotion_ready: false, limitations: data.limitations, experiment}, {headers: {"Content-Disposition": `attachment; filename="allocation-${experiment.id}.json"`, "Cache-Control": "no-store"}});
}
