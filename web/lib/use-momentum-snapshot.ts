"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { isMomentumDashboard, momentumDashboardForDate, shouldReplaceMomentumSnapshot, type MomentumDashboard } from "./momentum-types";

export function useMomentumSnapshot(original: MomentumDashboard) {
  const [snapshot, setSnapshot] = useState(original);
  const [now, setNow] = useState<Date | undefined>();
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);
  const request = useRef(0);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    setSnapshot(previous => shouldReplaceMomentumSnapshot(previous, original) ? original : previous);
  }, [original]);
  const refresh = useCallback(async () => {
    const sequence = ++request.current;
    controller.current?.abort();
    const active = new AbortController();
    controller.current = active;
    setRefreshing(true);
    setNow(new Date());
    try {
      const response = await fetch("/api/momentum", {
        cache: "no-store", signal: AbortSignal.any([active.signal, AbortSignal.timeout(15_000)]),
      });
      if (!response.ok) throw new Error("Snapshot unavailable");
      const payload: unknown = await response.json();
      if (!payload || typeof payload !== "object" || !("data" in payload) || !isMomentumDashboard(payload.data)
        || Date.parse(payload.data.generated_at_utc) > Date.now()) throw new Error("Invalid snapshot");
      if (sequence !== request.current) return;
      const next = payload.data;
      setSnapshot(previous => shouldReplaceMomentumSnapshot(previous, next) ? next : previous);
      setError(null);
      setLastChecked(new Date().toISOString());
      setNow(new Date());
    } catch {
      if (sequence === request.current && !active.signal.aborted) {
        setError("Could not load a newer snapshot. Last verified data is shown while it remains current.");
      }
    } finally {
      if (sequence === request.current) setRefreshing(false);
    }
  }, []);
  useEffect(() => {
    const tick = () => { void refresh(); };
    const timer = window.setInterval(tick, 60_000);
    window.addEventListener("focus", tick);
    setNow(new Date());
    return () => {window.clearInterval(timer); window.removeEventListener("focus", tick); ++request.current; controller.current?.abort();};
  }, [refresh]);
  return {data: now ? momentumDashboardForDate(snapshot, now) : snapshot, refresh, refreshing, error, lastChecked};
}
