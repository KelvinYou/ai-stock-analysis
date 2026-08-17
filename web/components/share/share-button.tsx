"use client";

import * as React from "react";
import { Check, Copy, Download, Loader2, Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

type Orientation = "landscape" | "portrait";
type ActionStatus = "idle" | "working" | "done" | "error";

const ACTION_LABEL: Record<"image" | "text" | "share" | "download", Record<ActionStatus, string>> = {
  image: { idle: "Copy image", working: "Copying…", done: "Copied", error: "Failed" },
  text: { idle: "Copy text", working: "Copying…", done: "Copied", error: "Failed" },
  share: { idle: "Share link", working: "Sharing…", done: "Shared", error: "Failed" },
  download: { idle: "Download", working: "Saving…", done: "Saved", error: "Failed" },
};

/**
 * Every image the dialog can show or hand off is this same route — the one
 * `og:image` unfurls with — parameterised by orientation. Nothing here ever
 * builds a card client-side; the browser only ever asks the server "what does
 * this ticker look like right now."
 */
function imageUrl(symbol: string, orientation: Orientation): string {
  return `/${encodeURIComponent(symbol)}/share-image?orientation=${orientation}`;
}

/**
 * Clicking Share no longer forwards an image sight-unseen: it opens a review
 * dialog with the actual rendered card, a landscape/portrait toggle, and three
 * independent hand-offs (image, text, link) so the reader picks what a given
 * destination actually wants instead of getting whatever `navigator.share`
 * decided to do with a PNG.
 */
export function ShareButton({
  symbol,
  shareText,
  className,
}: {
  symbol: string;
  shareText: string;
  className?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [orientation, setOrientation] = React.useState<Orientation>("landscape");
  const [status, setStatus] = React.useState<ActionStatus>("idle");
  const [pendingAction, setPendingAction] = React.useState<keyof typeof ACTION_LABEL | null>(null);
  const blobCache = React.useRef<Map<Orientation, Promise<Blob>>>(new Map());

  const pageUrl = React.useMemo(
    () => (typeof window === "undefined" ? "" : new URL(`/${symbol}`, window.location.origin).toString()),
    [symbol],
  );

  React.useEffect(() => {
    blobCache.current = new Map();
  }, [symbol]);

  function fetchBlob(target: Orientation): Promise<Blob> {
    const cached = blobCache.current.get(target);
    if (cached) return cached;
    const promise = fetch(imageUrl(symbol, target)).then((res) => {
      if (!res.ok) throw new Error(`card ${res.status}`);
      return res.blob();
    });
    promise.catch(() => blobCache.current.delete(target));
    blobCache.current.set(target, promise);
    return promise;
  }

  function settle(ok: boolean) {
    setStatus(ok ? "done" : "error");
    setTimeout(() => {
      setStatus("idle");
      setPendingAction(null);
    }, 1800);
  }

  async function run(action: keyof typeof ACTION_LABEL, task: () => Promise<void>) {
    setPendingAction(action);
    setStatus("working");
    try {
      await task();
      settle(true);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setStatus("idle");
        setPendingAction(null);
        return;
      }
      settle(false);
    }
  }

  const copyImage = () =>
    run("image", async () => {
      const blob = await fetchBlob(orientation);
      if (typeof ClipboardItem === "undefined" || !navigator.clipboard?.write) {
        throw new Error("clipboard image writes unsupported");
      }
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    });

  const copyText = () =>
    run("text", async () => {
      await navigator.clipboard.writeText(shareText);
    });

  const shareLink = () =>
    run("share", async () => {
      const blob = await fetchBlob(orientation);
      const file = new File([blob], `${symbol}-briefing.png`, { type: "image/png" });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: `${symbol} · briefing`, url: pageUrl, text: shareText });
        return;
      }
      if (navigator.share) {
        await navigator.share({ title: `${symbol} · briefing`, url: pageUrl, text: shareText });
        return;
      }
      throw new Error("navigator.share unsupported");
    });

  const download = () =>
    run("download", async () => {
      const blob = await fetchBlob(orientation);
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = `${symbol}-briefing-${orientation}.png`;
      a.click();
      URL.revokeObjectURL(objectUrl);
    });

  const canNativeShare = typeof navigator !== "undefined" && !!navigator.share;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setStatus("idle");
          setPendingAction(null);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={`Share ${symbol} briefing`}
          className={cn("gap-1.5", className)}
        >
          <Share2 aria-hidden />
          Share
        </Button>
      </DialogTrigger>

      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Share {symbol}</DialogTitle>
          <DialogDescription>
            Rendered fresh from the current briefing — review before it goes anywhere.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={orientation} onValueChange={(v) => setOrientation(v as Orientation)}>
          <TabsList className="w-fit">
            <TabsTrigger value="landscape">Landscape</TabsTrigger>
            <TabsTrigger value="portrait">Portrait</TabsTrigger>
          </TabsList>
        </Tabs>

        <div
          className={cn(
            "overflow-hidden rounded-lg border bg-secondary",
            orientation === "portrait" ? "mx-auto aspect-[4/5] max-w-[280px]" : "aspect-[16/9]",
          )}
        >
          {/* Re-mounts on orientation change so a slow fetch never shows the
              wrong card frozen under the new tab's label. */}
          <img
            key={`${symbol}-${orientation}`}
            src={imageUrl(symbol, orientation)}
            alt={`${symbol} share card preview, ${orientation}`}
            className="size-full object-contain"
          />
        </div>

        <DialogFooter className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <ActionButton
            icon={<Copy aria-hidden />}
            label={ACTION_LABEL.image[pendingAction === "image" ? status : "idle"]}
            busy={pendingAction === "image" && status === "working"}
            done={pendingAction === "image" && status === "done"}
            onClick={copyImage}
          />
          <ActionButton
            icon={<Copy aria-hidden />}
            label={ACTION_LABEL.text[pendingAction === "text" ? status : "idle"]}
            busy={pendingAction === "text" && status === "working"}
            done={pendingAction === "text" && status === "done"}
            onClick={copyText}
          />
          {canNativeShare && (
            <ActionButton
              icon={<Share2 aria-hidden />}
              label={ACTION_LABEL.share[pendingAction === "share" ? status : "idle"]}
              busy={pendingAction === "share" && status === "working"}
              done={pendingAction === "share" && status === "done"}
              onClick={shareLink}
            />
          )}
          <ActionButton
            icon={<Download aria-hidden />}
            label={ACTION_LABEL.download[pendingAction === "download" ? status : "idle"]}
            busy={pendingAction === "download" && status === "working"}
            done={pendingAction === "download" && status === "done"}
            onClick={download}
          />
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ActionButton({
  icon,
  label,
  busy,
  done,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  busy: boolean;
  done: boolean;
  onClick: () => void;
}) {
  return (
    <Button type="button" variant="secondary" size="sm" disabled={busy} onClick={onClick} className="gap-1.5">
      {busy ? <Loader2 className="animate-spin" aria-hidden /> : done ? <Check aria-hidden /> : icon}
      <span aria-live="polite">{label}</span>
    </Button>
  );
}
