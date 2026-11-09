import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api";

export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((value) => value + 1), []);
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    setLoading(Boolean(path));
    if (path)
      api<T>(path)
        .then((data) => {
          if (active) setData(data);
        })
        .catch((error) => {
          if (active) setError(errorMessage(error));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    return () => {
      active = false;
    };
  }, [path, version]);
  return { data, loading, error, reload };
}
