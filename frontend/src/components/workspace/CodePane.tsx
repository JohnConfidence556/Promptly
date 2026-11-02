import { Check, Copy } from "lucide-react";
import hljs from "highlight.js/lib/core";
import css from "highlight.js/lib/languages/css";
import javascript from "highlight.js/lib/languages/javascript";
import xml from "highlight.js/lib/languages/xml";
import "highlight.js/styles/github-dark.css";
import { useMemo, useState } from "react";

hljs.registerLanguage("xml", xml);
hljs.registerLanguage("css", css);
hljs.registerLanguage("javascript", javascript);

const FILE_ORDER = ["index.html", "style.css", "script.js"] as const;

const LANGUAGE: Record<string, string> = {
  "index.html": "xml",
  "style.css": "css",
  "script.js": "javascript",
};

type FileName = (typeof FILE_ORDER)[number];

export default function CodePane({ files }: { files: Record<string, string> | null }) {
  const [active, setActive] = useState<FileName>("index.html");
  const [copied, setCopied] = useState(false);

  const code = files?.[active] ?? "";
  const html = useMemo(
    () => hljs.highlight(code, { language: LANGUAGE[active] }).value,
    [code, active],
  );

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be blocked; nothing else to do.
    }
  }

  if (!files) {
    return (
      <div className="flex-1 space-y-2 p-4">
        {[0, 1, 2, 3, 4, 5].map((line) => (
          <div key={line} className="h-4 animate-pulse rounded bg-ink-900" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-ink-800 px-3">
        <div className="flex items-center gap-1" role="tablist" aria-label="Files">
          {FILE_ORDER.map((name) => (
            <button
              key={name}
              type="button"
              role="tab"
              aria-selected={active === name}
              onClick={() => setActive(name)}
              className={`rounded-lg px-2.5 py-1 font-mono text-xs transition-colors ${
                active === name ? "bg-ink-800 text-white" : "text-ink-400 hover:text-white"
              }`}
            >
              {name}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 text-xs text-ink-400">
          <span>{code.split("\n").length} lines</span>
          <button
            type="button"
            onClick={copy}
            className="flex items-center gap-1.5 rounded-lg px-2 py-1 transition-colors hover:text-white"
          >
            {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      <pre className="min-h-0 flex-1 overflow-auto p-4 font-mono text-[13px] leading-6">
        <code className="hljs" dangerouslySetInnerHTML={{ __html: html }} />
      </pre>
    </div>
  );
}