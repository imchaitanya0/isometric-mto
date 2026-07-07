/**
 * useJobPolling — polls GET /api/mto/{jobId} every 1.5s until completed or failed.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchJobStatus } from "@/lib/api";
import type { MTOResult } from "@/lib/schema";

type PollingState = "idle" | "polling" | "completed" | "failed";

interface UseJobPollingReturn {
  state: PollingState;
  result: MTOResult | null;
  error: string | null;
  startPolling: (jobId: string) => void;
  reset: () => void;
}

export function useJobPolling(): UseJobPollingReturn {
  const [state, setState] = useState<PollingState>("idle");
  const [result, setResult] = useState<MTOResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const jobIdRef = useRef<string | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const poll = useCallback(async () => {
    if (!jobIdRef.current) return;
    try {
      const data = await fetchJobStatus(jobIdRef.current);
      if (data.status === "completed" && data.result) {
        stopPolling();
        setResult(data.result);
        setState("completed");
      } else if (data.status === "failed") {
        stopPolling();
        setError(data.error || "Processing failed. Please try again.");
        setState("failed");
      }
      // if still "processing" — keep polling
    } catch (err) {
      stopPolling();
      setError(err instanceof Error ? err.message : "Network error");
      setState("failed");
    }
  }, [stopPolling]);

  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling();
      jobIdRef.current = jobId;
      setState("polling");
      setResult(null);
      setError(null);

      // Poll immediately, then every 1.5s
      poll();
      intervalRef.current = setInterval(poll, 1500);
    },
    [poll, stopPolling]
  );

  const reset = useCallback(() => {
    stopPolling();
    jobIdRef.current = null;
    setState("idle");
    setResult(null);
    setError(null);
  }, [stopPolling]);

  // Cleanup on unmount
  useEffect(() => () => stopPolling(), [stopPolling]);

  return { state, result, error, startPolling, reset };
}
