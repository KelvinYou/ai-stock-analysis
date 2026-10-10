import { loadAllocationResearch } from "@/lib/allocation-data";
import { AllocationDesk } from "@/components/allocation/allocation-desk";
export const metadata = {title: "Allocation · Desk", description: "Momentum allocation and historical research, with explicit uncertainty."};
export const dynamic = "force-dynamic";
export default async function AllocationPage() {
  const {data, error} = await loadAllocationResearch();
  if (!data) return <section className="space-y-3"><p className="eyebrow">Portfolio research</p><h1 className="text-3xl font-semibold text-ink">Allocation</h1><p role="status" className="text-sm text-graphite">{error}</p></section>;
  return <AllocationDesk data={data} />;
}
