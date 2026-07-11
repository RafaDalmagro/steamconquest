import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col gap-4 pt-16 text-center">
      <h1 className="text-2xl font-semibold uppercase tracking-wide">
        Página não encontrada
      </h1>
      <p className="text-muted-foreground">
        O endereço acessado não existe ou o link está quebrado.
      </p>
      <Link to="/" className="text-primary hover:underline">
        Voltar para o início
      </Link>
    </div>
  );
}
