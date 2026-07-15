import type {
  HTMLAttributes,
  ReactNode,
} from "react";

interface GlassPanelProps
  extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
  as?: "section" | "article" | "div";
  padding?: "none" | "sm" | "md" | "lg";
  interactive?: boolean;
}

const paddingClasses = {
  none: "",
  sm: "p-4",
  md: "p-6",
  lg: "p-7 lg:p-8",
};

export default function GlassPanel({
  children,
  as = "section",
  padding = "md",
  interactive = false,
  className = "",
  ...props
}: GlassPanelProps) {
  const Component = as;

  return (
    <Component
      {...props}
      className={[
        "relative overflow-hidden",
        "rounded-[2rem]",
        "border border-white/70",
        "bg-white/72",
        "shadow-[0_18px_45px_rgba(15,23,42,0.06)]",
        "backdrop-blur-2xl",
        "transition duration-300",
        interactive
          ? [
              "hover:-translate-y-1",
              "hover:bg-white/88",
              "hover:shadow-[0_28px_70px_rgba(15,23,42,0.1)]",
            ].join(" ")
          : "",
        paddingClasses[padding],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div
        aria-hidden="true"
        className={[
          "pointer-events-none absolute inset-x-8 top-0",
          "h-px",
          "bg-gradient-to-r",
          "from-transparent via-white to-transparent",
        ].join(" ")}
      />

      <div className="relative">
        {children}
      </div>
    </Component>
  );
}