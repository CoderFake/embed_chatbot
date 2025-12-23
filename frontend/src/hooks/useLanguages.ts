import { useEffect, useState } from "react";
import { commonAPI, Language } from "@/lib/api/common";

export function useLanguages() {
  const [languages, setLanguages] = useState<Language[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLanguages();
  }, []);

  const fetchLanguages = async () => {
    try {
      setLoading(true);
      const data = await commonAPI.getLanguages();
      setLanguages(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch languages');
      console.error("Failed to fetch languages:", err);
    } finally {
      setLoading(false);
    }
  };

  return { languages, loading, error };
}

