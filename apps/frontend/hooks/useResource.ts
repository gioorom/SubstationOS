"use client";

/**
 * The two state primitives every screen in this application is built
 * from.
 *
 * Before this EPIC each hook hand-rolled its own `loading` / `error` /
 * `reload` triple, five times, each with a slightly different definition
 * of what an error was and none of them cancelling anything. That is the
 * duplication Phase 9 removes: a resource is a read that can be
 * refreshed, and a mutation is a write that reports its own outcome.
 *
 * Both cancel in-flight work on unmount and when their inputs change, so
 * a superseded response can never overwrite a newer one.
 *
 * **Callers must pass stable functions** - `read` and `perform` wrapped
 * in `useCallback`, and `copy` declared as a module constant. That is
 * what makes the dependency arrays honest and keeps these hooks free of
 * the render-time ref writes the React compiler rejects.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { describeError, isCancellation } from "@/lib/api";
import type { ErrorCopy } from "@/lib/api";

export interface ResourceState<T> {
  data: T | null;
  /** True only on the first load; a refresh sets `refreshing` instead. */
  loading: boolean;
  refreshing: boolean;
  /** A user-facing sentence, or `null`. Never a raw status code. */
  error: string | null;
  /** The typed failure, for callers that need to branch on the cause. */
  failure: unknown;
  reload: () => Promise<void>;
  /** Replaces the cached value without a round trip (post-mutation). */
  set: (value: T | null) => void;
}

export interface ResourceOptions {
  /** When false the read is not performed - an unresolved route param. */
  enabled?: boolean;
  /** Must be referentially stable; declare it as a module constant. */
  copy?: ErrorCopy;
}

const NO_COPY: ErrorCopy = {};

/**
 * Reads a value from the backend and keeps it fresh.
 *
 * `read` is given an `AbortSignal` and must pass it to the resource
 * function, so a superseded request is actually cancelled rather than
 * merely ignored.
 */
export function useResource<T>(
  read: (signal: AbortSignal) => Promise<T>,
  options: ResourceOptions = {},
): ResourceState<T> {
  const enabled = options.enabled ?? true;
  const copy = options.copy ?? NO_COPY;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<unknown>(null);

  const loadedOnce = useRef(false);
  const controller = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    controller.current?.abort();

    const current = new AbortController();
    controller.current = current;

    // The pending flags are applied in a microtask rather than
    // synchronously, so the effect that schedules a load does not also
    // trigger a render of its own. `loading` already starts at `enabled`,
    // so nothing flashes while we wait for this tick.
    await Promise.resolve();

    if (current.signal.aborted) {
      return;
    }

    if (!enabled) {
      setLoading(false);
      return;
    }

    if (loadedOnce.current) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    setError(null);
    setFailure(null);

    try {
      const value = await read(current.signal);

      if (current.signal.aborted) {
        return;
      }

      setData(value);
      loadedOnce.current = true;
    } catch (caught) {
      if (isCancellation(caught) || current.signal.aborted) {
        return;
      }

      setData(null);
      setFailure(caught);
      setError(describeError(caught, copy));
    } finally {
      if (!current.signal.aborted) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [enabled, read, copy]);

  useEffect(() => {
    // `react-hooks/set-state-in-effect` guards against effects that
    // derive state React could have computed during render. This is the
    // other case the rule cannot distinguish: subscribing to an external
    // system - the backend - whose answer arrives later and must be put
    // somewhere. `load` awaits before touching state, and the effect
    // aborts the request it started.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();

    return () => controller.current?.abort();
  }, [load]);

  return {
    data,
    loading,
    refreshing,
    error,
    failure,
    reload: load,
    set: setData,
  };
}

export interface MutationState<Input, Output> {
  run: (input: Input) => Promise<Output>;
  pending: boolean;
  error: string | null;
  /** The typed failure - a `ValidationError` carries its field messages. */
  failure: unknown;
  reset: () => void;
}

/**
 * Performs a write and reports its outcome.
 *
 * `run` **re-throws** so a caller can branch on the failure (navigate on
 * success, keep the form open on 422) while `error` and `failure` stay
 * available for rendering. Swallowing the rejection here would force
 * every call site to inspect state instead of using `try`/`catch`.
 */
export function useMutation<Input, Output>(
  perform: (input: Input, signal: AbortSignal) => Promise<Output>,
  options: { copy?: ErrorCopy } = {},
): MutationState<Input, Output> {
  const copy = options.copy ?? NO_COPY;

  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<unknown>(null);

  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const run = useCallback(
    async (input: Input): Promise<Output> => {
      controller.current?.abort();

      const current = new AbortController();
      controller.current = current;

      setPending(true);
      setError(null);
      setFailure(null);

      try {
        return await perform(input, current.signal);
      } catch (caught) {
        if (!isCancellation(caught)) {
          setFailure(caught);
          setError(describeError(caught, copy));
        }

        throw caught;
      } finally {
        setPending(false);
      }
    },
    [perform, copy],
  );

  const reset = useCallback(() => {
    setError(null);
    setFailure(null);
  }, []);

  return { run, pending, error, failure, reset };
}
