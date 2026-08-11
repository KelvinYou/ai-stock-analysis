"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

/** Inline shell command with a copy button — for "run this to fill the gap" hints. */
export function CopyCommand({
  command,
  className,
}: {
  command: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked (non-HTTPS origin, denied permission) — the command
      // is still visible and selectable, so there is nothing to recover from.
    }
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border bg-muted/60 py-1 pl-2.5 pr-1",
        className,
      )}
    >
      <code className="font-mono text-[11px] text-foreground">{command}</code>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? "Copied" : `Copy: ${command}`}
        className="rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        {copied ? (
          <Check className="size-3 text-emerald-600" />
        ) : (
          <Copy className="size-3" />
        )}
      </button>
    </span>
  );
}
