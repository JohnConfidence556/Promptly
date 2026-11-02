import { ChevronDown, Clock, Coins, Hourglass, Wrench } from "lucide-react";
import { useEffect, useState } from "react";

import { listRuns, type RunSummary } from "../../lib/api";
import { formatNumber, formatSeconds, timeAgo } from "../../lib/format";
import { useSession } from "../../lib/session";

const STEP_NAMES: Record<string, string> = {
  planner: "Planner",
  architect: "Architect",
  coder: "Coder",
  validator: "Validator",
  repairer: "Repair",
  writer: "Save",
  edit_planner: "Edit planner",
  editor: "Editor",
  give_up: "Gave up",
};

function RunCard({ run }: { run: RunSummary }) {
  const [open, setOpen] = useState(false);
  const longest = Math.max(1, ...run.steps.map((step) => step.seconds));
  const failed = run.status === "failed";

  return (
    <li className="rounded-2xl border border-ink-700 bg-ink-900/60">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="w-full p-3 text-left"
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-xs ${
                run.kind === "build"
                  ? "bg-brand-500/15 text-brand-300"
                  : "bg-sky-500/15 text-sky-300"
              }`}
            >
              {run.kind === "build" ? "Build" : "Edit"}
            </span>
            <span className={`text-xs ${failed ? "text-red-400" : "text-emerald-400"}`}>
              {failed ? "Failed" : "Passed"}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-ink-400">
            {timeAgo(run.created_at)}
            <ChevronDown
              className={`size-4 transition-transform ${open ? "rotate-180" : ""}`}
            />
          </div>
        </div>

        <p className="mt-2 truncate text-sm text-ink-200">{run.prompt}</p>

        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-400">
          <span className="flex items-center gap-1">
            <Clock className="size-3.5" />
            {formatSeconds(run.duration_seconds)}
          </span>
          <span className="flex items-center gap-1">
            <Coins className="size-3.5" />
            {formatNumber(run.prompt_tokens + run.completion_tokens)} tokens
          </span>
          <span>
            {run.llm_calls} LLM call{run.llm_calls === 1 ? "" : "s"}
          </span>
          {run.wait_seconds > 0 && (
            <span className="flex items-center gap-1 text-amber-300">
              <Hourglass className="size-3.5" />
              {formatSeconds(run.wait_seconds)} waiting on rate limits
            </span>
          )}
          {run.fix_rounds > 0 && (
            <span className="flex items-center gap-1">
              <Wrench className="size-3.5" />
              {run.fix_rounds} fix round{run.fix_rounds === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </button>

      {open && (
        <div className="border-t border-ink-800 p-3">
          <ul className="space-y-3">
            {run.steps.map((step, index) => (
              <li key={`${step.step}-${index}`}>
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="text-ink-200">{STEP_NAMES[step.step] ?? step.step}</span>
                  <span className="text-ink-400">
                    {formatSeconds(step.seconds)} ·{" "}
                    {formatNumber(step.prompt_tokens + step.completion_tokens)} tokens
                    {step.waited > 0 ? ` · waited ${formatSeconds(step.waited)}` : ""}
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink-800">
                  <div
                    className="h-full rounded-full bg-brand-500/70"
                    style={{ width: `${Math.max(2, (step.seconds / longest) * 100)}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>

          {run.error && (
            <p className="mt-3 whitespace-pre-wrap break-words text-xs text-red-300">
              {run.error}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

type Props = { projectId: string | null; refreshKey: number };

export default function RunLogPane({ projectId, refreshKey }: Props) {
  const { session } = useSession();
  const token = session?.token ?? "";
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;

    let cancelled = false;

    listRuns(token, projectId)
      .then((data) => {
        if (!cancelled) setRuns(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load the run log.");
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, token, refreshKey]);

  if (error) {
    return <p className="p-4 text-sm text-red-300">{error}</p>;
  }

  if (runs === null) {
    return (
      <div className="space-y-3 p-4">
        {[0, 1].map((item) => (
          <div key={item} className="h-24 animate-pulse rounded-2xl bg-ink-900" />
        ))}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-ink-400">
        Every build and edit is recorded here, with its time, tokens and fix rounds.
      </div>
    );
  }

  return (
    <ul className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
      {runs.map((run) => (
        <RunCard key={run.id} run={run} />
      ))}
    </ul>
  );
}