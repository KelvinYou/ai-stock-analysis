import { redirect } from "next/navigation";

/** The screener moved to `/`. Kept so bookmarked /dashboard links still land. */
export default function DashboardRedirect() {
  redirect("/");
}
