import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";

import { cn } from "@/lib/utils";

// Overlay de blocos: "recorta" o fill em segmentos usando o fundo da barra.
const SEGMENTED =
  "after:pointer-events-none after:absolute after:inset-0 after:bg-[repeating-linear-gradient(90deg,transparent_0,transparent_10px,var(--background)_10px,var(--background)_12px)]";

function Progress({
  className,
  value,
  segmented,
  complete,
  ...props
}: React.ComponentProps<typeof ProgressPrimitive.Root> & {
  segmented?: boolean;
  complete?: boolean;
}) {
  return (
    <ProgressPrimitive.Root
      value={value}
      className={cn(
        "relative h-2 w-full overflow-hidden bg-background",
        segmented && SEGMENTED,
        className,
      )}
      {...props}
    >
      <ProgressPrimitive.Indicator
        className={cn(
          "h-full transition-all",
          complete ? "bg-achieved" : "bg-primary",
        )}
        style={{ transform: `translateX(-${100 - (value ?? 0)}%)` }}
      />
    </ProgressPrimitive.Root>
  );
}

export { Progress };
