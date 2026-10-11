import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { devicesKey } from "@/lib/queryKeys";

import { api } from "./client";

// /api/devices (SPEC F2, §6.3): the user's devices, created by the ingest; only the name changes.

export type Device = {
  id: string;
  external_id: string;
  kind: "watch" | "phone";
  name: string;
  created_at: string;
  last_data_at: string | null;
};

export function useDevices() {
  return useQuery({ queryKey: devicesKey, queryFn: () => api.get<Device[]>("/api/devices") });
}

export function useRenameDevice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      api.patch<Device>(`/api/devices/${id}`, { name }),
    onSuccess: (device) => {
      queryClient.setQueryData<Device[]>(devicesKey, (old) =>
        old?.map((d) => (d.id === device.id ? device : d)),
      );
      void queryClient.invalidateQueries({ queryKey: devicesKey });
    },
  });
}
