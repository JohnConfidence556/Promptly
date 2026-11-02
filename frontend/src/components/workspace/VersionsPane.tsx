import { Loader2, RotateCcw } from "lucide-react";
import { useState } from "react";

import type { VersionSummary } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import Button from "../ui/Button";

type Props = {
  versions: VersionSummary[];
  selected: number | null;
  disabled: boolean;
  onSelect: (number: number) => void;
  onRestore: (number: number) => Promise<void>;
};

export default function VersionsPane({
  versions,
  selected,
  disabled,
  onSelect,
  onRestore,
}: Props) {
  const [restoring, setRestoring] = useState<number | null>(null);
  const latest = versions.length ? versions[versions.length - 1].number : null;

  async function restore(number: number) {
    setRestoring(number);
    try {
      await onRestore(number);
    } finally {
      setRestoring(null);
    }
  }

  if (versions.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-ink-400">
        Versions will appear here after your first build.
      </div>
    );
  }

  return (
    <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">
      {[...versions].reverse().map((version) => {
        const isSelected = version.number === selected;

        return (
          <li
            key={version.number}
            className={`rounded-xl border p-3 ${
              isSelected ? "border-brand-500/60 bg-brand-500/5" : "border-ink-700 bg-ink-900/60"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-white">Version {version.number}</span>
                {version.number === latest && (
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300">
                    Latest
                  </span>
                )}
                {isSelected && (
                  <span className="rounded-full bg-brand-500/15 px-2 py-0.5 text-xs text-brand-300">
                    Viewing
                  </span>
                )}
              </div>
              <span className="text-xs text-ink-400">{timeAgo(version.created_at)}</span>
            </div>

            <p className="mt-1.5 line-clamp-2 text-sm text-ink-300">{version.prompt}</p>

            <div className="mt-3 flex gap-2">
              {!isSelected && (
                <Button size="sm" variant="secondary" onClick={() => onSelect(version.number)}>
                  View
                </Button>
              )}
              {version.number !== latest && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={disabled || restoring !== null}
                  onClick={() => restore(version.number)}
                >
                  {restoring === version.number ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <RotateCcw className="size-4" />
                  )}
                  Restore
                </Button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}