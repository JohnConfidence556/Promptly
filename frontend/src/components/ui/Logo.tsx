import { Zap } from "lucide-react";

export default function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span className="flex size-7 items-center justify-center rounded-lg bg-linear-to-br from-brand-500 to-indigo-500 text-white shadow-md shadow-brand-600/30">
        <Zap className="size-4" />
      </span>
      <span className="text-[17px] font-semibold tracking-tight text-white">Promptly</span>
    </span>
  );
}