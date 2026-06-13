import { api } from "./client";
import type { UserCreate, UserOut, UserUpdate } from "./types";

export const usersApi = {
  list: (): Promise<UserOut[]> => api.get<UserOut[]>("/users"),
  create: (payload: UserCreate): Promise<UserOut> => api.post<UserOut>("/users", payload),
  update: (userId: string, payload: UserUpdate): Promise<UserOut> =>
    api.patch<UserOut>(`/users/${userId}`, payload),
};
