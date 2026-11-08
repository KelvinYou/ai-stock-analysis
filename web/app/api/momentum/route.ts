import { loadMomentumDashboard } from "@/lib/momentum-data";

export const dynamic = "force-dynamic";
export async function GET() {
  const result = await loadMomentumDashboard();
  return Response.json(result, {
    status: result.data ? 200 : 503,
    headers: {"Cache-Control": "no-store"},
  });
}
