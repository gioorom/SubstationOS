/**
 * The backend contract, in one place.
 *
 * Every enum, request body and response body the frontend consumes is
 * declared under `lib/contracts` and nowhere else. A component that needs
 * to know the valid project statuses imports `PROJECT_STATUSES` from
 * here; it does not write `"planning" | "active"` inline, and a test
 * asserts that the enums here match the backend's OpenAPI document.
 */

export * from "./document";
export * from "./graph";
export * from "./identity";
export * from "./pagination";
export * from "./pipeline";
export * from "./platform";
export * from "./project";
export * from "./review";
