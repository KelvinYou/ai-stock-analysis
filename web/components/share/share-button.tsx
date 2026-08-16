"use client";

import * as React from "react";
import { Check, Loader2, Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Status = "idle" | "working" | "shared" | "copied" | "saved" | "error";

const LABEL: Record<Status, string> = {
  idle: "Share",
  working: "Preparing…",
  shared: "Shared",
  copied: "Copied",
  saved: "Saved",
  error: "Failed",
};

/**
 * Fetches this ticker's Open Graph card and hands it to whatever the platform
 * actually supports, in descending order of usefulness:
 *
 *   1. the native share sheet with the PNG attached — phones, where sharing an
 *      image is the whole point
 *   2. the clipboard as an image — desktop Chrome/Edge, so it can be pasted
 *      straight into Slack or a doc
 *   3. a download — everything else, including desktop Safari and Firefox
 *
 * The image is the same one the link unfurls with, because it is literally the
 * same route.
 */
export function ShareButton({
  symbol,
  className,
}: {
  symbol: string;
  className?: string;
}) {
  const [status, setStatus] = React.useState<Status>("idle");
  const pending = React.useRef<Promise<Blob> | null>(null);

  React.useEffect(() => {
    // A new ticker invalidates whatever card was warmed for the last one.
    pending.current = null;
    setStatus("idle");
  }, [symbol]);

  const imageUrl = `/${encodeURIComponent(symbol)}/opengraph-image`;

  /**
   * Start the fetch on hover/focus rather than on click. Safari consumes the
   * transient activation that `navigator.share()` requires if too much awaiting
   * happens between the tap and the call, so the blob wants to be in hand
   * before the click, not after it.
   */
  function warm() {
    pending.current ??= fetch(imageUrl).then((res) => {
      if (!res.ok) throw new Error(`card ${res.status}`);
      return res.blob();
    });
    // A warm-up that fails must not surface as an unhandled rejection; the
    // click path will retry and report properly.
    pending.current.catch(() => {
      pending.current = null;
    });
  }

  async function share() {
    setStatus("working");
    try {
      warm();
      const blob = await pending.current!;
      const file = new File([blob], `${symbol}-briefing.png`, { type: "image/png" });
      const url = new URL(`/${symbol}`, window.location.origin).toString();

      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: `${symbol} · briefing`, url });
        setStatus("shared");
        return;
      }

      if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        setStatus("copied");
        return;
      }

      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = file.name;
      a.click();
      URL.revokeObjectURL(objectUrl);
      setStatus("saved");
    } catch (err) {
      // Dismissing the share sheet rejects with AbortError. That is a decision,
      // not a failure, and the button should look untouched afterwards.
      if (err instanceof DOMException && err.name === "AbortError") {
        setStatus("idle");
        return;
      }
      pending.current = null;
      setStatus("error");
    }
  }

  React.useEffect(() => {
    if (status === "idle" || status === "working") return;
    const t = setTimeout(() => setStatus("idle"), 2200);
    return () => clearTimeout(t);
  }, [status]);

  const settled = status === "shared" || status === "copied" || status === "saved";

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={share}
      onPointerEnter={warm}
      onFocus={warm}
      disabled={status === "working"}
      aria-label={`Share ${symbol} briefing as an image`}
      className={cn("gap-1.5", className)}
    >
      {status === "working" ? (
        <Loader2 className="animate-spin" aria-hidden />
      ) : settled ? (
        <Check aria-hidden />
      ) : (
        <Share2 aria-hidden />
      )}
      {/* The label carries the outcome, so the state change is announced rather
          than left to the icon swap. */}
      <span aria-live="polite">{LABEL[status]}</span>
    </Button>
  );
}
