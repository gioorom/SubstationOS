import type { InputHTMLAttributes } from "react";

interface InputProps
  extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
}

export default function Input({
  id,
  label,
  helperText,
  error,
  className = "",
  ...props
}: InputProps) {
  const inputId = id ?? props.name;

  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={inputId}
          className="mb-2 block text-sm font-medium text-[var(--text-secondary)]"
        >
          {label}
        </label>
      )}

      <input
        {...props}
        id={inputId}
        className={[
          "focus-ring",
          "w-full rounded-[var(--radius-sm)]",
          "border bg-white",
          "px-4 py-3",
          "text-sm text-[var(--text-primary)]",
          "placeholder:text-[var(--text-tertiary)]",
          error
            ? "border-[var(--danger)]"
            : "border-[var(--border-strong)]",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
      />

      {error ? (
        <p className="mt-2 text-sm text-[var(--danger)]">
          {error}
        </p>
      ) : helperText ? (
        <p className="mt-2 text-sm text-[var(--text-tertiary)]">
          {helperText}
        </p>
      ) : null}
    </div>
  );
}