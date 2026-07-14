"use client";

import type { MouseEvent, ReactNode } from "react";
import { useState } from "react";

interface DashboardStatCardProps {
  title: string;
  value: string | number;
  subtitle: string;
  icon: ReactNode;
  trend?: string;
}

export default function DashboardStatCard({
  title,
  value,
  subtitle,
  icon,
  trend,
}: DashboardStatCardProps) {
  const [transform, setTransform] = useState(
    "perspective(900px) rotateX(0deg) rotateY(0deg)"
  );

  function handleMouseMove(
    event: MouseEvent<HTMLElement>
  ) {
    const card = event.currentTarget;
    const rect = card.getBoundingClientRect();

    const x =
      (event.clientX - rect.left) / rect.width;
    const y =
      (event.clientY - rect.top) / rect.height;

    const rotateY = (x - 0.5) * 8;
    const rotateX = (0.5 - y) * 8;

    setTransform(
      `perspective(900px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`
    );
  }

  function resetTransform() {
    setTransform(
      "perspective(900px) rotateX(0deg) rotateY(0deg)"
    );
  }

  return (
    <section
      onMouseMove={handleMouseMove}
      onMouseLeave={resetTransform}
      style={{ transform }}
      className={[
        "group relative overflow-hidden",
        "rounded-3xl border border-white/70",
        "bg-white/72 p-5",
        "shadow-[0_18px_45px_rgba(15,23,42,0.06)]",
        "backdrop-blur-2xl",
        "transition-[transform,box-shadow,background-color]",
        "duration-200 ease-out",
        "hover:bg-white/88",
        "hover:shadow-[0_28px_70px_rgba(15,23,42,0.12)]",
      ].join(" ")}
    >
      <div
        aria-hidden="true"
        className={[
          "pointer-events-none absolute -right-10 -top-10",
          "h-28 w-28 rounded-full",
          "bg-primary/12 blur-3xl",
          "transition duration-300",
          "group-hover:scale-125 group-hover:bg-primary/18",
        ].join(" ")}
      />

      <div
        aria-hidden="true"
        className={[
          "pointer-events-none absolute inset-x-6 top-0",
          "h-px bg-gradient-to-r",
          "from-transparent via-white to-transparent",
        ].join(" ")}
      />

      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-muted-foreground">
            {title}
          </p>

          <p className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
            {value}
          </p>

          <p className="mt-2 text-sm text-muted-foreground">
            {subtitle}
          </p>
        </div>

        <div
          className={[
            "flex h-12 w-12 items-center justify-center",
            "rounded-2xl bg-primary/10 text-primary",
            "shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]",
            "transition duration-300",
            "group-hover:scale-110 group-hover:bg-primary/15",
          ].join(" ")}
        >
          {icon}
        </div>
      </div>

      {trend && (
        <div className="relative mt-5 inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-100">
          {trend}
        </div>
      )}
    </section>
  );
}