import { Check, Info, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

import type { StepView } from "../../lib/steps";
import type { FileProgress, Waiting } from "../../lib/stream";

function StepIcon({ step }: { step: StepView }) {
  if (step.status === "running") {
    return <Loader2 className="size-4 animate-spin text-brand-400" />;
  }
  if (step.status === "failed") return <X className="size-4 text-red-400" />;
  if (step.tone === "warn") return <Info className="size-4 text-amber-400" />;
  return <Check className="size-4 text-emerald-400" />;
}

function fileLabel(item: FileProgress): string {
  const done = item.state === "done";

  switch (item.action) {
    case "fix":
      return done ? `${item.file} fixed` : `Fixing ${item.file}…`;
    case "edit":
      return done ? `${item.file} updated` : `Editing ${item.file}…`;
    default:
      return done ? `${item.file} written` : `Writing ${item.file}…`;
  }
}

function FileRows({ files }: { files: FileProgress[] }) {
  return (
    <ul className="ml-6 mt-1.5 space-y-1">
      {files.map((item) => (
        <li
          key={item.file}
          className={`flex items-center gap-1.5 text-xs ${
            item.state === "done" ? "text-ink-400" : "text-ink-100"
          }`}
        >
          {item.state === "done" ? (
            <Check className="size-3.5 text-emerald-400" />
          ) : (
            <Loader2 className="size-3.5 animate-spin text-brand-400" />
          )}
          {fileLabel(item)}
        </li>
      ))}
    </ul>
  );
}

function WaitingRow({ waiting }: { waiting: Waiting }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, []);

  const remaining = Math.max(0, Math.ceil(waiting.seconds - (now - waiting.since) / 1000));
  const reason =
    waiting.reason === "rate_limit"
      ? "Waiting for the AI provider's rate limit"
      : "Retrying after a hiccup";

  return (
    <div className="ml-6 mt-1.5 flex items-center gap-1.5 text-xs text-amber-300">
      <Info className="size-3.5 shrink-0" />
      {reason} · {remaining > 0 ? `retrying in ${remaining}s` : "retrying now"}
    </div>
  );
}

export default function StepList({ steps }: { steps: StepView[] }) {
  return (
    <ul className="mt-2 space-y-1.5">
      {steps.map((step) => (
        <li key={step.key} className="text-sm">
          <div
            className={`flex items-start gap-2 ${
              step.status === "running" ? "text-white" : "text-ink-300"
            }`}
          >
            <span className="mt-0.5 shrink-0">
              <StepIcon step={step} />
            </span>
            <span>{step.label}</span>
          </div>

          {step.files && step.files.length > 0 && <FileRows files={step.files} />}

          {step.waiting && <WaitingRow key={step.waiting.since} waiting={step.waiting} />}

          {step.details && step.details.length > 0 && (
            <ul className="ml-6 mt-1 space-y-0.5 text-xs text-ink-400">
              {step.details.map((detail, index) => (
                <li key={index} className="break-words">
                  {detail}
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}