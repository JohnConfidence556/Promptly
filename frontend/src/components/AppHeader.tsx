import { LogOut } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { initials } from "../lib/format";
import { useSession } from "../lib/session";
import Button from "./ui/Button";
import Logo from "./ui/Logo";

export default function AppHeader() {
  const { session, signOut } = useSession();
  const navigate = useNavigate();
  const name = session?.user.name ?? "";

  function handleSignOut() {
    const confirmed = window.confirm(
      "Sign out? Your projects are tied to this browser, so you won't be able to get back to them.",
    );
    if (!confirmed) return;

    signOut();
    navigate("/");
  }

  return (
    <header className="sticky top-0 z-20 border-b border-ink-800 bg-ink-950/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link to="/home" aria-label="Promptly home">
          <Logo />
        </Link>
        <div className="flex items-center gap-3">
          <span className="hidden text-sm text-ink-300 sm:block">{name}</span>
          <div className="flex size-8 items-center justify-center rounded-full bg-brand-500/20 text-xs font-medium text-brand-300">
            {initials(name)}
          </div>
          <Button variant="ghost" size="sm" onClick={handleSignOut}>
            <LogOut className="size-4" />
            Sign out
          </Button>
        </div>
      </div>
    </header>
  );
}