// /api/devices (SPEC F2, §6.3): the user's devices, created by the ingest; only the name changes.

export type Device = {
  id: string;
  external_id: string;
  kind: "watch" | "phone";
  name: string;
  created_at: string;
  last_data_at: string | null;
};
