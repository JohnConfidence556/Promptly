import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import Button from "../components/ui/Button";
import Field from "../components/ui/Field";
import Logo from "../components/ui/Logo";
import { ApiError, signUp } from "../lib/api";
import { useSession } from "../lib/session";

type Errors = { name?: string; email?: string; form?: string };

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function GetStarted() {
  const { session, signIn } = useSession();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [loading, setLoading] = useState(false);

  if (session) return <Navigate to="/home" replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const next: Errors = {};
    if (!name.trim()) next.name = "Enter your name";
    if (!EMAIL_PATTERN.test(email.trim())) next.email = "Enter a valid email address";

    setErrors(next);
    if (next.name || next.email) return;

    setLoading(true);
    try {
      const { user, token } = await signUp(name.trim(), email.trim());
      signIn({ token, user });
      navigate("/home", { replace: true });
    } catch (error) {
      setErrors({
        form:
          error instanceof ApiError
            ? error.message
            : "Couldn't reach Promptly. Check your connection and try again.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-6">
      <div
        className="hero-glow pointer-events-none absolute inset-x-0 top-0 h-[480px]"
        aria-hidden
      />
      <div className="relative w-full max-w-md animate-fade-up">
        <Link to="/" className="mb-8 flex justify-center" aria-label="Promptly">
          <Logo />
        </Link>

        <form
          onSubmit={handleSubmit}
          noValidate
          className="rounded-2xl border border-ink-700 bg-ink-900/80 p-8 backdrop-blur"
        >
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            Welcome to Promptly
          </h1>
          <p className="mt-2 text-sm text-ink-300">
            Tell us who you are so your projects are waiting for you next time.
          </p>

          <div className="mt-6 space-y-4">
            <Field
              label="Your name"
              autoComplete="name"
              placeholder="Ada Lovelace"
              value={name}
              error={errors.name}
              onChange={(event) => setName(event.target.value)}
              maxLength={80}
            />
            <Field
              label="Email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              error={errors.email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>

          {errors.form && (
            <p role="alert" className="mt-4 text-sm text-red-400">
              {errors.form}
            </p>
          )}

          <Button type="submit" size="lg" loading={loading} className="mt-6 w-full">
            Continue
          </Button>

          <p className="mt-4 text-center text-xs text-ink-400">
                        Your projects are saved in this browser. We store your name, email, and prompts to run
                        Promptly, and prompts are also logged to a monitoring tool to help improve it.
          </p>
        </form>
      </div>
    </div>
  );
}