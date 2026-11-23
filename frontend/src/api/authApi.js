import api from "./axiosInstance";
export const login  = (d) => api.post("/api/auth/login",    d);
export const register=(d) => api.post("/api/auth/register", d);
export const logout  = () => api.post("/api/auth/logout");
export const getMe   = () => api.get("/api/auth/me");
export const updateMe= (d) => api.put("/api/auth/me", d);
