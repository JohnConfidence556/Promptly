import {
  ArrowRight,
  Check,
  Code,
  Download,
  History,
  Loader2,
  MessageSquare,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";

import { buttonClasses } from "../components/ui/Button";
import Logo from "../components/ui/Logo";
import { useSession } from "../lib/session";

const STEPS = [
  {
    icon: MessageSquare,
    title: "Describe it",
    body: "Say what you want in plain English: a timer, a calculator, a to-do list.",
  },
  {
    icon: Sparkles,
    title: "Watch it build",
    body: "Promptly plans the app, writes the HTML, CSS, and JavaScript, and checks the result.",
  },
  {
    icon: History,
    title: "Refine it",
    body: "Ask for changes in the chat. Each change becomes a new version you can go back to.",
  },
];

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "Checks its own work",
    body: "Every build is validated against a shared plan between files. When something is off, Promptly fixes it before you see it.",
  },
  {
    icon: History,
    title: "Every change is a version",
    body: "Ask for a change and get a new version. Restore any earlier one whenever you want.",
  },
  {
    icon: Download,
    title: "Take the code with you",
    body: "Download your app as plain files and host it anywhere.",
  },
  {
    icon: Code,
    title: "Plain web code",
    body: "HTML, CSS, and JavaScript. No frameworks to learn and nothing to install.",
  },
];

const KEYS = ["7", "8", "9", "÷", "4", "5", "6", "×", "1", "2", "3", "−"];

function ProductPreview() {
  return (
    <div className="mx-auto mt-16 max-w-5xl animate-fade-up rounded-2xl border border-ink-700 bg-ink-900/80 p-2 shadow-2xl shadow-brand-600/10">
      <div className="overflow-hidden rounded-xl border border-ink-700 bg-ink-950">
        <div className="flex h-10 items-center gap-2 border-b border-ink-800 px-4">
          <span className="size-2.5 rounded-full bg-ink-600" />
          <span className="size-2.5 rounded-full bg-ink-600" />
          <span className="size-2.5 rounded-full bg-ink-600" />
          <span className="ml-3 text-xs text-ink-400">Simple calculator · v2</span>
        </div>
        <div className="grid min-h-[320px] grid-cols-1 md:grid-cols-[300px_1fr]">
          <div className="space-y-3 border-b border-ink-800 bg-ink-900/60 p-4 text-left text-sm md:border-r md:border-b-0">
            <div className="ml-auto w-fit max-w-[85%] rounded-xl border border-ink-700 bg-ink-800 px-3 py-2 text-ink-100">
              Make the number buttons orange
            </div>
            <div className="space-y-1.5 rounded-xl border border-ink-700 bg-ink-800/60 p-3 text-ink-300">
              <div className="flex items-center gap-2">
                <Check className="size-4 text-emerald-400" />
                Planned the change
              </div>
              <div className="flex items-center gap-2 text-ink-100">
                <Loader2 className="size-4 animate-spin text-brand-400" />
                Editing style.css
              </div>
            </div>
          </div>
          <div className="flex items-center justify-center bg-ink-900/30 p-6">
            <div className="w-56 rounded-2xl border border-ink-700 bg-ink-900 p-3">
              <div className="mb-3 rounded-lg border border-ink-700 bg-ink-950 px-3 py-2 text-right text-xl text-white">
                128
              </div>
              <div className="grid grid-cols-4 gap-2 text-center text-sm">
                {KEYS.map((key) => (
                  <div
                    key={key}
                    className={`rounded-lg py-2 ${
                      /\d/.test(key)
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-brand-500/20 text-brand-300"
                    }`}
                  >
                    {key}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Landing() {
  const { session } = useSession();
  const target = session ? "/home" : "/get-started";
  const label = session ? "Open your projects" : "Get started";

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div
        className="hero-glow pointer-events-none absolute inset-x-0 top-0 h-[640px]"
        aria-hidden
      />

      <header className="relative mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <Logo />
        <Link to={target} className={buttonClasses("secondary", "sm")}>
          {label}
        </Link>
      </header>

      <main className="relative">
        <section className="mx-auto max-w-4xl px-6 pt-16 text-center sm:pt-24">
          <p className="animate-fade-up text-sm font-medium text-brand-300">
            Describe it. Watch it build.
          </p>
          <h1 className="mt-4 animate-fade-up text-4xl font-semibold tracking-tight text-white sm:text-6xl">
            Turn a sentence into a working app
          </h1>
          <p className="mx-auto mt-6 max-w-2xl animate-fade-up text-lg text-ink-300">
            Promptly plans, writes, and checks a small web app from your description. Then you
            keep refining it in plain English.
          </p>
          <div className="mt-10 flex animate-fade-up flex-wrap items-center justify-center gap-3">
            <Link to={target} className={buttonClasses("primary", "lg")}>
              {label}
              <ArrowRight className="size-4" />
            </Link>
            <a href="#how" className={buttonClasses("ghost", "lg")}>
              See how it works
            </a>
          </div>
        </section>

        <div className="px-6">
          <ProductPreview />
        </div>

        <section id="how" className="mx-auto max-w-6xl px-6 py-28">
          <h2 className="text-center text-3xl font-semibold tracking-tight text-white">
            From idea to app in three steps
          </h2>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, body }, index) => (
              <div key={title} className="rounded-2xl border border-ink-700 bg-ink-900/60 p-6">
                <div className="flex items-center gap-3">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300">
                    <Icon className="size-5" />
                  </span>
                  <span className="text-sm text-ink-400">Step {index + 1}</span>
                </div>
                <h3 className="mt-4 text-lg font-medium text-white">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-300">{body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 pb-28">
          <div className="grid gap-4 sm:grid-cols-2">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <div key={title} className="flex gap-4 rounded-2xl border border-ink-800 p-6">
                <Icon className="mt-0.5 size-5 shrink-0 text-brand-400" />
                <div>
                  <h3 className="font-medium text-white">{title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ink-300">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-3xl px-6 pb-28 text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-white">
            Ready to build something?
          </h2>
          <Link to={target} className={buttonClasses("primary", "lg", "mt-8")}>
            {label}
            <ArrowRight className="size-4" />
          </Link>
        </section>
      </main>

      <footer className="relative border-t border-ink-800 py-8 text-center text-sm text-ink-400">
        © 2026 Promptly
      </footer>
    </div>
  );
}