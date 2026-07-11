import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// SteamID64 tem 17 dígitos. O backend revalida (422); aqui é só UX.
const STEAMID_RE = /^\d{17}$/;
const STORAGE_KEY = "lastSteamId";

export function Home() {
  const navigate = useNavigate();
  const [value, setValue] = useState(
    () => localStorage.getItem(STORAGE_KEY) ?? "",
  );
  const [error, setError] = useState<string | null>(null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const id = value.trim();
    if (!STEAMID_RE.test(id)) {
      setError("Informe um SteamID64 válido (17 dígitos).");
      return;
    }
    localStorage.setItem(STORAGE_KEY, id);
    navigate(`/u/${id}`);
  };

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6 pt-16">
      <div>
        <h1 className="text-2xl font-semibold uppercase tracking-wide">
          Suas conquistas Steam
        </h1>
        <p className="mt-1 text-muted-foreground">
          Informe seu SteamID64 para ver biblioteca e progresso.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-3">
        <label htmlFor="steamid" className="text-sm font-medium">
          Steam ID
        </label>
        <Input
          id="steamid"
          inputMode="numeric"
          autoComplete="off"
          placeholder="76561197960287930"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
        />
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" variant="active">
          Ver biblioteca
        </Button>
      </form>
    </div>
  );
}
