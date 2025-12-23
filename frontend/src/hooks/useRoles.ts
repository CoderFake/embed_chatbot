import { useEffect, useState } from "react";
import { commonAPI, Role } from "@/lib/api/common";

export function useRoles() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRoles();
  }, []);

  const fetchRoles = async () => {
    try {
      setLoading(true);
      const data = await commonAPI.getRoles();
      setRoles(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch roles');
      console.error("Failed to fetch roles:", err);
    } finally {
      setLoading(false);
    }
  };

  return { roles, loading, error };
}

