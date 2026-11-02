import { ChevronDown, Download, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { VersionSummary } from "../../lib/api";
import { initials, timeAgo } from "../../lib/format";
import { useSession } from "../../lib/session";
import Button from "../ui/Button";
import Logo from "../ui/Logo";

function VersionPicker({
  versions,
  selected,
  onSelect,
}: {
  versions: VersionSummary[];
  selected: number;
  onSelect: (number: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const latest = versions.length ? versions[versions.length - 1].number : null;

  useEffect(() => {
    if (!open) return;

    function close(event: MouseEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-lg bg-brand-500/15 px-2.5 py-1 text-sm text-brand-300 transition-colors hover:bg-brand-500/25"
      >
        v{selected}
        <ChevronDown className="size-3.5" />
      </button>

      {open && (
        <ul
          role="listbox"
          aria-label="Versions"
          className="absolute left-0 top-full z-30 mt-2 max-h-72 w-64 overflow-auto rounded-xl border border-ink-700 bg-ink-900 p-1 shadow-xl"
        >
          {[...versions].reverse().map((version) => (
            <li key={version.number}>
              <button
                type="button"
                role="option"
                aria-selected={version.number === selected}
                onClick={() => {
                  onSelect(version.number);
                  setOpen(false);
                }}
                className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-ink-800 ${
                  version.number === selected ? "text-white" : "text-ink-300"
                }`}
              >
                <span>
                  Version {version.number}
                  {version.number === latest ? " (latest)" : ""}
                </span>
                <span className="text-xs text-ink-400">{timeAgo(version.created_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

type Props = {
  title: string;
  versions: VersionSummary[];
  selected: number | null;
  canDownload: boolean;
  downloading: boolean;
  onSelect: (number: number) => void;
  onDownload: () => void;
};

export default function WorkspaceHeader({
  title,
  versions,
  selected,
  canDownload,
  downloading,
  onSelect,
  onDownload,
}: Props) {
  const { session } = useSession();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-ink-800 bg-ink-950 px-4">
      <div className="flex min-w-0 items-center gap-3">
        <Link to="/home" aria-label="Back to your projects" className="shrink-0">
          <Logo />
        </Link>
        <span className="text-ink-600">/</span>
        <h1 className="truncate text-sm font-medium text-white">{title}</h1>
        {selected !== null && (
          <VersionPicker versions={versions} selected={selected} onSelect={onSelect} />
        )}
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={onDownload}
          disabled={!canDownload || downloading}
        >
          {downloading ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
          Download
        </Button>
        <div className="flex size-8 items-center justify-center rounded-full bg-brand-500/20 text-xs font-medium text-brand-300">
          {initials(session?.user.name ?? "")}
        </div>
      </div>
    </header>
  );
}