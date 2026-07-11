import type * as React from "react";

import { cn } from "@/lib/utils";

export function Message({
  children,
  className,
  role,
}: {
  children: React.ReactNode;
  className?: string;
  // role="alert" nos erros para leitores de tela anunciarem; ausente nas
  // mensagens meramente informativas.
  role?: "alert" | "status";
}) {
  return (
    <p role={role} className={cn("py-8 text-center text-muted-foreground", className)}>
      {children}
    </p>
  );
}
