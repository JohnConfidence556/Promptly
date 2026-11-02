import { ExternalLink, Loader2, Monitor, RotateCw, Smartphone, Tablet } from "lucide-react";
import { useState, type CSSProperties } from "react";

import { fileUrl } from "../../lib/api";

const DEVICES = [
  { id: "desktop", label: "Desktop", icon: Monitor, width: "100%" },
  { id: "tablet", label: "Tablet", icon: Tablet, width: "768px" },
  { id: "mobile", label: "Mobile", icon: Smartphone, width: "390px" },
] as const;

type DeviceId = (typeof DEVICES)[number]["id"];

// Plain inline styles on purpose. They pin an element to the corners of its frame
// without relying on percentage heights, which collapse inside nested flex layouts.
const FILL: CSSProperties = {
  position: "absolute",
  top: 0,
  left: 0,
  width: "100%",
  height: "100%",
  border: 0,
};

function FramedApp({ url, title }: { url: string; title: string }) {
  const [loaded, setLoaded] = useState(false);

  return (
    <>
      <iframe
        src={url}
        title={title}
        onLoad={() => setLoaded(true)}
        sandbox="allow-scripts allow-same-origin"
        style={{ ...FILL, background: "#ffffff" }}
      />
      {!loaded && (
        <div
          style={FILL}
          className="pointer-events-none z-10 flex items-center justify-center bg-ink-900"
        >
          <Loader2 className="size-5 animate-spin text-ink-400" />
        </div>
      )}
    </>
  );
}

function EmptyPreview({ building }: { building: boolean }) {
  if (!building) {
    return (
      <div className="flex w-full items-center justify-center text-sm text-ink-400">
        Nothing to preview yet.
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col items-center justify-center gap-4 text-center">
      <div className="w-full animate-pulse space-y-3 rounded-2xl border border-ink-700 bg-ink-900 p-5">
        <div className="h-4 w-1/3 rounded bg-ink-700" />
        <div className="h-24 rounded-xl bg-ink-800" />
        <div className="grid grid-cols-3 gap-2">
          <div className="h-8 rounded-lg bg-ink-800" />
          <div className="h-8 rounded-lg bg-ink-800" />
          <div className="h-8 rounded-lg bg-ink-800" />
        </div>
      </div>
      <p className="text-sm text-ink-300">Your app will appear here as soon as it's ready.</p>
    </div>
  );
}

type Props = {
  projectId: string | null;
  version: number | null;
  title: string;
  building: boolean;
};

export default function PreviewPane({ projectId, version, title, building }: Props) {
  const [device, setDevice] = useState<DeviceId>("desktop");
  const [reloadKey, setReloadKey] = useState(0);

  const url = projectId && version ? fileUrl(projectId, version, "index.html") : null;
  const width = DEVICES.find((item) => item.id === device)?.width ?? "100%";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-ink-800 px-3">
        <div className="flex items-center gap-1" role="group" aria-label="Preview size">
          {DEVICES.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setDevice(id)}
              aria-label={label}
              aria-pressed={device === id}
              className={`rounded-lg p-1.5 transition-colors ${
                device === id ? "bg-ink-800 text-white" : "text-ink-400 hover:text-white"
              }`}
            >
              <Icon className="size-4" />
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          {building && url && (
            <span className="mr-2 flex items-center gap-1.5 text-xs text-brand-300">
              <Loader2 className="size-3.5 animate-spin" />
              Updating
            </span>
          )}
          <button
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
            disabled={!url}
            aria-label="Reload preview"
            className="rounded-lg p-1.5 text-ink-400 transition-colors hover:text-white disabled:opacity-40"
          >
            <RotateCw className="size-4" />
          </button>
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              aria-label="Open preview in a new tab"
              className="rounded-lg p-1.5 text-ink-400 transition-colors hover:text-white"
            >
              <ExternalLink className="size-4" />
            </a>
          )}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 justify-center overflow-hidden bg-ink-900/40 p-3">
        {url ? (
          <div
            className="overflow-hidden rounded-xl border border-ink-700 bg-white shadow-xl transition-[width] duration-300"
            style={{ position: "relative", width, maxWidth: "100%" }}
          >
            <FramedApp key={`${url}-${reloadKey}`} url={url} title={`${title} preview`} />
          </div>
        ) : (
          <EmptyPreview building={building} />
        )}
      </div>
    </div>
  );
}