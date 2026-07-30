/**
 * Client-side validation of the Project form.
 *
 * Every rule here restates a backend rule, and **only** a backend rule.
 * The limits come from `PROJECT_FIELD_LIMITS`, which is transcribed from
 * the Pydantic schema, so the form cannot refuse something the API would
 * accept - or accept something it would refuse.
 *
 * Its purpose is to fail fast, not to be authoritative: the backend's
 * 422 is still surfaced field by field when the two ever disagree.
 */

import {
  PROJECT_FIELD_LIMITS,
  PROJECT_STATUSES,
  type CreateProjectRequest,
  type ProjectStatus,
} from "@/lib/contracts";

export type ProjectFormValues = {
  name: string;
  code: string;
  customer: string;
  epc: string;
  country: string;
  location: string;
  voltage_level: string;
  status: ProjectStatus;
  description: string;
};

export const EMPTY_PROJECT_FORM: ProjectFormValues = {
  name: "",
  code: "",
  customer: "",
  epc: "",
  country: "",
  location: "",
  voltage_level: "",
  status: "planning",
  description: "",
};

export type FormErrors = Partial<
  Record<keyof ProjectFormValues, string>
>;

function checkLength(
  value: string,
  limits: { min: number; max: number },
  required: boolean,
): string | undefined {
  const trimmed = value.trim();

  if (trimmed === "") {
    return required ? "Campo obbligatorio." : undefined;
  }

  if (trimmed.length < limits.min) {
    return `Deve contenere almeno ${limits.min} caratteri.`;
  }

  if (trimmed.length > limits.max) {
    return `Non può superare ${limits.max} caratteri.`;
  }

  return undefined;
}

export function validateProjectForm(
  values: ProjectFormValues,
): FormErrors {
  const errors: FormErrors = {};

  const name = checkLength(
    values.name,
    PROJECT_FIELD_LIMITS.name,
    true,
  );

  if (name) errors.name = name;

  const code = checkLength(
    values.code,
    PROJECT_FIELD_LIMITS.code,
    true,
  );

  if (code) errors.code = code;

  // Required by the backend. The previous frontend treated it as
  // optional, which made every project created without a customer fail
  // validation at the API with no field-level explanation.
  const customer = checkLength(
    values.customer,
    PROJECT_FIELD_LIMITS.customer,
    true,
  );

  if (customer) errors.customer = customer;

  for (const field of [
    "epc",
    "country",
    "location",
    "voltage_level",
  ] as const) {
    const message = checkLength(
      values[field],
      PROJECT_FIELD_LIMITS[field],
      false,
    );

    if (message) errors[field] = message;
  }

  if (!PROJECT_STATUSES.includes(values.status)) {
    errors.status = "Valore non ammesso.";
  }

  return errors;
}

/** Blank optional fields are omitted rather than sent as `""`. */
function optional(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

export function toCreateRequest(
  values: ProjectFormValues,
): CreateProjectRequest {
  return {
    name: values.name.trim(),
    code: values.code.trim(),
    customer: values.customer.trim(),
    epc: optional(values.epc),
    country: optional(values.country),
    location: optional(values.location),
    voltage_level: optional(values.voltage_level),
    status: values.status,
    description: optional(values.description),
  };
}
