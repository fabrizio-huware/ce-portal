import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "./client";

const FIVE_MIN = 5 * 60_000;

export const useClients = () =>
  useQuery({
    queryKey: ["clients-lookup"],
    queryFn: async () => unwrap(await api.GET("/api/v1/clients/lookup", { params: { query: { limit: 200 } } })),
    staleTime: FIVE_MIN,
  });

export const useProfiles = () =>
  useQuery({
    queryKey: ["profiles-active"],
    queryFn: async () => unwrap(await api.GET("/api/v1/profiles", { params: { query: { is_active: true } } })),
    staleTime: FIVE_MIN,
  });

export const useEmployees = () =>
  useQuery({
    queryKey: ["employees-active"],
    queryFn: async () => unwrap(await api.GET("/api/v1/employees", { params: { query: { is_active: true, limit: 200 } } })).items,
    staleTime: FIVE_MIN,
  });
