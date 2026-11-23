import api from "./axiosInstance";
export const listProjects  = (p)   => api.get("/api/projects/",           { params: p });
export const getProject    = (id)  => api.get(`/api/projects/${id}`);
export const createProject = (d)   => api.post("/api/projects/",          d);
export const updateProject = (id,d)=> api.put(`/api/projects/${id}`,      d);
export const submitProject = (id)  => api.put(`/api/projects/${id}/submit`);
export const reviewProject = (id,d)=> api.put(`/api/projects/${id}/review`,d);
