import { ArrowUp } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import type { VersionSummary } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import { liveSteps, storedSteps } from "../../lib/steps";
import type { StreamState } from "../../lib/stream";
import type { LiveTurn } from "../../lib/workspace";
import Button from "../ui/Button";
import StepList from "./StepList";

type Props = {
  versions: VersionSummary[];
  selected: number | null;
  loading: boolean;
  live: LiveTurn | null;
  stream: StreamState;
  canSend: boolean;
  onSelect: (number: number) => void;
  onSend: (prompt: string) => void;
  onRetry: () => void;
  onDismiss: () => void;
};


const CLAMP_STYLE = {
  display: "-webkit-box",
  WebkitLineClamp: 5,
  WebkitBoxOrient: "vertical",
  overflow: "hidden",
} as const;

function PromptBubble({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = text.length > 240;

  return (
    <div className="ml-auto w-fit max-w-[88%]">
      <div className="rounded-2xl rounded-br-md border border-ink-700 bg-ink-800 px-3.5 py-2 text-sm leading-relaxed text-ink-100">
        <p
          className="whitespace-pre-wrap break-words"
          style={isLong && !expanded ? CLAMP_STYLE : undefined}
        >
          {text}
        </p>
      </div>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="ml-auto mt-1 block text-xs text-ink-400 transition-colors hover:text-white"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}


function StoredTurn({
  version,
  selected,
  onSelect,
}: {
  version: VersionSummary;
  selected: boolean;
  onSelect: () => void;
}) {
  const restored = version.prompt.startsWith("Restored version");

  return (
    <div className="space-y-3">
      {!restored && <PromptBubble text={version.prompt} />}
      <button
        type="button"
        onClick={onSelect}
        className={`w-full rounded-2xl border p-3 text-left transition-colors ${
          selected
            ? "border-brand-500/60 bg-brand-500/5"
            : "border-ink-700 bg-ink-900/60 hover:border-ink-500"
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm font-medium text-white">
            {restored ? version.prompt : `Version ${version.number}`}
          </span>
          <span className="shrink-0 text-xs text-ink-400">{timeAgo(version.created_at)}</span>
        </div>
        {!restored && <StepList steps={storedSteps(version)} />}
      </button>
    </div>
  );
}

function LiveTurnCard({
  live,
  stream,
  onRetry,
  onDismiss,
}: {
  live: LiveTurn;
  stream: StreamState;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  const running = stream.status === "running";
  const title = running
    ? live.kind === "build"
      ? "Building your app"
      : "Applying your change"
    : stream.status === "failed"
      ? "That didn't work"
      : "Done";

  return (
    <div className="space-y-3">
      <PromptBubble text={live.prompt} />
      <div className="rounded-2xl border border-ink-700 bg-ink-900/60 p-3">
        <div className="text-sm font-medium text-white">{title}</div>
        <StepList steps={liveSteps(live.kind, stream.steps, running, {files: stream.files, waiting: stream.waiting,})} />

        {stream.status === "failed" && (
          <div
            role="alert"
            className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"
          >
            <p className="whitespace-pre-wrap break-words text-xs leading-relaxed">
              {stream.error ?? "The build failed."}
            </p>
            <div className="mt-3 flex gap-2">
              <Button size="sm" variant="secondary" onClick={onRetry}>
                Try again
              </Button>
              <Button size="sm" variant="ghost" onClick={onDismiss}>
                Dismiss
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatPanel({
  versions,
  selected,
  loading,
  live,
  stream,
  canSend,
  onSelect,
  onSend,
  onRetry,
  onDismiss,
}: Props) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);

  // Only auto-scroll when the user is already near the bottom.
  useEffect(() => {
    const element = scrollRef.current;
    if (!element || !shouldAutoScrollRef.current) return;

    element.scrollTop = element.scrollHeight;
  }, [versions.length, stream.steps.length, stream.status, live]);

  function submit() {
    const text = draft.trim();
    if (text.length < 3 || !canSend) return;

    onSend(text);
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="absolute inset-0 grid grid-rows-[minmax(0,1fr)_auto]">
      <div ref={scrollRef} className="space-y-6 overflow-y-auto p-4">
    
        {loading && (
          <div className="space-y-3">
            <div className="ml-auto h-9 w-2/3 animate-pulse rounded-2xl bg-ink-900" />
            <div className="h-28 animate-pulse rounded-2xl bg-ink-900" />
          </div>
        )}

        {versions.map((version) => (
          <StoredTurn
            key={version.number}
            version={version}
            selected={version.number === selected}
            onSelect={() => onSelect(version.number)}
          />
        ))}

        {live && (
          <LiveTurnCard live={live} stream={stream} onRetry={onRetry} onDismiss={onDismiss} />
        )}
      </div>

      <div className="border-t border-ink-800 bg-ink-950 p-3">
        <div className="rounded-2xl border border-ink-600 bg-ink-900 p-2.5 focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/30">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            maxLength={2000}
            disabled={!canSend}
            aria-label="Ask Promptly to change something"
            placeholder={
              canSend ? "Ask Promptly to change something…" : "Promptly is working on it…"
            }
            className="w-full resize-none bg-transparent px-1.5 py-1 text-sm text-white placeholder:text-ink-400 focus:outline-none disabled:cursor-not-allowed"
          />
          <div className="flex items-center justify-between px-1.5 pt-1">
            <span className="text-xs text-ink-400">Enter to send</span>
            <Button size="sm" onClick={submit} disabled={!canSend || draft.trim().length < 3}>
              <ArrowUp className="size-4" />
              Send
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}