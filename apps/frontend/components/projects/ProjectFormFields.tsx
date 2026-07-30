"use client";

import type { FormErrors, ProjectFormValues } from "@/lib/validation/project";

interface FieldProps {
  id: keyof ProjectFormValues;
  label: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  maxLength?: number;
}

const inputClass =
  "w-full rounded-2xl border bg-white/80 px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:ring-4";

export function TextField({
  id,
  label,
  value,
  error,
  onChange,
  placeholder,
  required = false,
  maxLength,
}: FieldProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-2 block text-sm font-medium text-foreground"
      >
        {label}
        {required && <span className="ml-1 text-red-600">*</span>}
      </label>

      <input
        id={id}
        name={id}
        type="text"
        value={value}
        maxLength={maxLength}
        aria-invalid={error !== undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={[
          inputClass,
          error
            ? "border-red-400 focus:border-red-500 focus:ring-red-100"
            : "border-input focus:border-primary focus:ring-primary/10",
        ].join(" ")}
      />

      {error && (
        <p id={`${id}-error`} role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

export function TextAreaField({
  id,
  label,
  value,
  error,
  onChange,
  placeholder,
}: FieldProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-sm font-medium text-foreground"
      >
        {label}
      </label>

      <textarea
        id={id}
        name={id}
        rows={6}
        value={value}
        aria-invalid={error !== undefined}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={[
          "mt-2 resize-y",
          inputClass,
          error
            ? "border-red-400 focus:border-red-500 focus:ring-red-100"
            : "border-input focus:border-primary focus:ring-primary/10",
        ].join(" ")}
      />

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

interface SelectFieldProps<T extends string> {
  id: string;
  label: string;
  value: T;
  options: readonly T[];
  labels: Record<T, string>;
  error?: string;
  onChange: (value: T) => void;
}

/**
 * The options are generated from the contract's enum, so a status the
 * backend does not accept cannot be offered.
 */
export function SelectField<T extends string>({
  id,
  label,
  value,
  options,
  labels,
  error,
  onChange,
}: SelectFieldProps<T>) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-2 block text-sm font-medium text-foreground"
      >
        {label}
      </label>

      <select
        id={id}
        name={id}
        value={value}
        aria-invalid={error !== undefined}
        onChange={(event) => onChange(event.target.value as T)}
        className={[
          inputClass,
          error
            ? "border-red-400 focus:border-red-500 focus:ring-red-100"
            : "border-input focus:border-primary focus:ring-primary/10",
        ].join(" ")}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {labels[option]}
          </option>
        ))}
      </select>

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

export type { FormErrors, ProjectFormValues };
