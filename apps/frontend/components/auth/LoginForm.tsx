"use client";

import { useState } from "react";
import { LogIn } from "lucide-react";

import { Button } from "@/components/ui/button";
import { describeSignInFailure, useSession } from "@/hooks/useSession";

/**
 * The sign-in form.
 *
 * Two properties worth stating, because both are easy to lose:
 *
 * - **The password is never stored.** It lives in component state for
 *   the duration of the keystroke sequence and goes out in one request.
 *   Nothing writes it to `localStorage`, to a URL, or to a log.
 * - **The failure message never says which half was wrong.** The backend
 *   answers "no such account" and "wrong password" identically on
 *   purpose, and a UI that guessed a friendlier distinction would undo
 *   it - turning this form into a way to discover who has an account.
 */
export default function LoginForm() {
  const { signIn, expired } = useSession();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();

    setPending(true);
    setError(null);

    try {
      await signIn(email, password);
      // Deliberately cleared on success as well as on failure: there is
      // no reason for the password to outlive the request.
      setPassword("");
    } catch (caught) {
      setError(describeSignInFailure(caught));
      setPassword("");
    } finally {
      setPending(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="w-full max-w-sm space-y-5 rounded-3xl border border-slate-200 bg-white/80 p-8 shadow-sm"
      aria-labelledby="login-heading"
    >
      <div>
        <p className="text-sm font-medium text-primary">SubstationOS</p>

        <h1
          id="login-heading"
          className="mt-2 text-2xl font-semibold tracking-tight text-foreground"
        >
          Accedi
        </h1>

        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Questa è una piattaforma privata. Gli account sono creati da un
          amministratore.
        </p>
      </div>

      {expired && (
        <p
          role="status"
          className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
        >
          La sessione è scaduta. Effettua di nuovo l&apos;accesso per
          continuare.
        </p>
      )}

      <label className="block text-sm font-medium text-foreground">
        Email
        <input
          type="email"
          name="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="mt-1 h-10 w-full rounded-xl border border-input bg-background px-3 text-sm text-foreground"
        />
      </label>

      <label className="block text-sm font-medium text-foreground">
        Password
        <input
          type="password"
          name="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="mt-1 h-10 w-full rounded-xl border border-input bg-background px-3 text-sm text-foreground"
        />
      </label>

      {error !== null && (
        <p
          role="alert"
          className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </p>
      )}

      <Button type="submit" className="w-full" disabled={pending}>
        <LogIn className="h-4 w-4" />
        {pending ? "Accesso in corso…" : "Accedi"}
      </Button>
    </form>
  );
}
