"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { z } from "zod";
import { ApiError, eventUrl, loadInputs, loadSnapshot, startRun } from "@/lib/api";
import { eventSchema, eventTypes, isTerminal, type DemoInput } from "@/lib/contracts";
import { initialRunState, projectRun, runReducer } from "@/lib/run-state";

export type Connection = "checking" | "connected" | "live" | "reconnecting" | "offline";
const pendingKey = "tender-demo-pending-start";
const pendingSchema = z.object({ key: z.string().min(1), inputId: z.string().min(1) });
type PendingStart = z.infer<typeof pendingSchema>;

function rememberPending(value: PendingStart | null): void {
  try { if (value) sessionStorage.setItem(pendingKey, JSON.stringify(value)); else sessionStorage.removeItem(pendingKey); }
  catch { /* In-memory recovery remains available if browser storage is disabled. */ }
}

/** One accepted run, one stream. Reconnects never POST another analysis. */
export function useTenderRun() {
  const [state, dispatch] = useReducer(runReducer, initialRunState);
  const [inputs, setInputs] = useState<DemoInput[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [connection, setConnection] = useState<Connection>("checking");
  const [problem, setProblem] = useState<ApiError | null>(null);
  const [starting, setStarting] = useState(false);
  const [pending, setPending] = useState<PendingStart | null>(null);
  const [retry, setRetry] = useState(0);
  const [now, setNow] = useState<number | null>(null);
  const startLock = useRef(false);
  const mounted = useRef(false);
  const startController = useRef<AbortController | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; startController.current?.abort(); };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function initialize() {
      // Reading browser state happens after hydration, without an automatic start.
      const restored = new URL(window.location.href).searchParams.get("run");
      let saved: PendingStart | null = null;
      try { const parsed = pendingSchema.safeParse(JSON.parse(sessionStorage.getItem(pendingKey) || "null")); saved = parsed.success ? parsed.data : null; }
      catch { /* An unavailable/corrupt local entry cannot authorize a new run. */ }
      try {
        const list = await loadInputs(controller.signal);
        if (!controller.signal.aborted) { setInputs(list); setConnection("connected"); }
      } catch (error) {
        if (!controller.signal.aborted) { setConnection("offline"); setProblem(error as ApiError); }
      }
      if (controller.signal.aborted) return;
      if (restored) {
        if (z.uuid().safeParse(restored).success) setRunId(restored);
        else setProblem(new ApiError("INVALID_RUN", "This run link is invalid. Return to a new analysis."));
      }
      setPending(saved);
    }
    void initialize();
    return () => controller.abort();
  }, [retry]);

  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    let source: EventSource | null = null;
    let checking = false;
    let terminal = false;
    let streamBroken = false;
    let lastRecovery = 0;

    async function refresh() {
      const snapshot = await loadSnapshot(runId!, controller.signal);
      if (controller.signal.aborted) return null;
      dispatch({ type: "snapshot", snapshot });
      if (isTerminal(snapshot)) { terminal = true; source?.close(); setConnection("connected"); }
      return snapshot;
    }

    function contractFailure() {
      streamBroken = true;
      source?.close();
      setConnection("offline");
      setProblem(new ApiError("INVALID_EVENT", "A live update could not be read. Reconnect to restore this run safely."));
    }

    async function connect() {
      try {
        const snapshot = await refresh();
        if (!snapshot || controller.signal.aborted || terminal) return;
        // Replay this run's small event history so a refreshed client demo
        // still shows the steps already completed. The reducer deduplicates IDs.
        source = new EventSource(eventUrl(runId!, 0));
        source.onopen = () => { if (!controller.signal.aborted && !terminal) { setConnection("live"); setProblem(null); } };
        for (const kind of eventTypes) {
          source.addEventListener(kind, (message: MessageEvent) => {
            if (controller.signal.aborted || terminal || streamBroken) return;
            let parsed: ReturnType<typeof eventSchema.safeParse>;
            try { parsed = eventSchema.safeParse(JSON.parse(message.data)); } catch { contractFailure(); return; }
            if (!parsed.success || parsed.data.type !== kind || parsed.data.run_id !== runId) { contractFailure(); return; }
            dispatch({ type: "event", event: parsed.data });
            const finished = kind === "run.completed" || kind === "run.failed";
            if (finished) { terminal = true; source?.close(); setConnection("connected"); }
            if (finished || kind === "worker.completed" || kind === "worker.failed") {
              void refresh().catch(error => { if (!controller.signal.aborted) setProblem(error as ApiError); });
            }
          });
        }
        source.onerror = () => {
          if (controller.signal.aborted || terminal || streamBroken) return;
          setConnection("reconnecting");
          // Let EventSource replay on recovery, but also detect lost/expired runs.
          if (checking || Date.now() - lastRecovery < 4000) return;
          checking = true; lastRecovery = Date.now();
          void refresh().catch((error: ApiError) => {
            if (controller.signal.aborted) return;
            if (["RUN_NOT_FOUND", "INVALID_RESPONSE", "INVALID_CURSOR"].includes(error.code)) {
              source?.close(); streamBroken = true; setConnection("offline"); setProblem(error);
            }
          }).finally(() => { checking = false; });
        };
      } catch (error) {
        if (!controller.signal.aborted) { setConnection("offline"); setProblem(error as ApiError); }
      }
    }
    void connect();
    return () => { controller.abort(); source?.close(); };
  }, [runId, retry]);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    const onPopState = () => {
      const id = new URL(window.location.href).searchParams.get("run");
      const nextRunId = id && z.uuid().safeParse(id).success ? id : null;
      // Section anchors also trigger history events. Preserve the active run
      // when navigating within this page; only a different run needs a reset.
      if (nextRunId === runId) return;
      dispatch({ type: "reset" });
      setRunId(nextRunId);
    };
    window.addEventListener("popstate", onPopState);
    return () => { clearInterval(timer); window.removeEventListener("popstate", onPopState); };
  }, [runId]);

  const snapshot = useMemo(() => projectRun(state), [state]);
  const active = starting || (!!runId && (!snapshot || !isTerminal(snapshot)));
  const start = useCallback(async (inputId: string) => {
    if (startLock.current || active) return;
    startLock.current = true; setStarting(true); setProblem(null);
    const attempt = pending || { key: crypto.randomUUID(), inputId };
    setPending(attempt); rememberPending(attempt);
    const controller = new AbortController(); startController.current = controller;
    try {
      const accepted = await startRun(attempt.inputId, attempt.key, controller.signal);
      if (!mounted.current || controller.signal.aborted) return;
      rememberPending(null); setPending(null);
      dispatch({ type: "reset" }); setRunId(accepted.run_id); setConnection("checking");
      const url = new URL(window.location.href); url.searchParams.set("run", accepted.run_id);
      window.history.replaceState({}, "", url);
    } catch (error) {
      if (!mounted.current || controller.signal.aborted) return;
      const failure = error as ApiError;
      if (failure.status >= 400 && failure.status < 500) { rememberPending(null); setPending(null); setProblem(failure); }
      else setProblem(new ApiError("START_UNCONFIRMED", "The start response was not confirmed. Use Recover run to retry safely with the same request key."));
    } finally { startLock.current = false; if (mounted.current) setStarting(false); }
  }, [active, pending]);

  const reconnect = () => { setProblem(null); setConnection("checking"); setRetry(value => value + 1); };
  const clearRun = () => {
    const url = new URL(window.location.href); url.searchParams.delete("run"); window.history.replaceState({}, "", url);
    dispatch({ type: "reset" }); setRunId(null); setProblem(null); setRetry(value => value + 1);
  };
  const elapsed = snapshot?.duration_ms ?? (now && snapshot?.started_at ? Math.max(0, now - Date.parse(snapshot.started_at)) : null);
  return { snapshot, events: state.events, inputs, runId, connection, problem, starting, active, pending,
    elapsed, start, reconnect, clearRun };
}
