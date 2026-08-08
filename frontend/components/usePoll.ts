"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function usePoll<T>(
  fetcher: () => Promise<T>,
  intervalMs = 15000,
  key: unknown = ""
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetcherRef = useRef(fetcher);
  const dirtyRef = useRef(true);

  const run = useCallback(async () => {
    if (dirtyRef.current) {
      setLoading(true);
      dirtyRef.current = false;
    }
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  useEffect(() => {
    dirtyRef.current = true;
    void run();
    const timer = setInterval(() => void run(), intervalMs);
    return () => clearInterval(timer);
  }, [run, intervalMs, key]);

  return { data, loading, error, refetch: run };
}
