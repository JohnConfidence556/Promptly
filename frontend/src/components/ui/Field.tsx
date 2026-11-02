import { useId, type InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
};

export default function Field({ label, error, className = "", ...input }: Props) {
  const id = useId();

  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink-200">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`h-11 w-full rounded-xl border bg-ink-950 px-3.5 text-sm text-white placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40 ${
          error ? "border-red-500/60" : "border-ink-600 focus:border-brand-500"
        } ${className}`}
        {...input}
      />
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-xs text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}