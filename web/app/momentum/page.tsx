import { MomentumDesk } from "@/components/allocation/momentum-desk";
import { loadMomentumDashboard } from "@/lib/momentum-data";

export const metadata = {title: "Momentum Allocation · Desk", description: "Price-only monthly targets and daily momentum rankings. No AI required."};
export const dynamic = "force-dynamic";

export default async function MomentumPage() {
  const {data, error} = await loadMomentumDashboard();
  if (!data) return <section className="space-y-4"><p className="eyebrow">Price-only strategy</p><h1 className="text-3xl font-semibold text-ink">Momentum Allocation</h1><p role="status" className="text-sm text-graphite">{error}</p></section>;
  return <MomentumDesk data={data} />;
}
