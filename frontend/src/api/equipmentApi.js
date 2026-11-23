import api from "./axiosInstance";
export const listEquipment  = (p) => api.get("/api/equipment/",           { params: p });
export const getEquipment   = (id)=> api.get(`/api/equipment/${id}`);
export const getAvailability= (id,p)=>api.get(`/api/equipment/${id}/availability`, { params: p });
export const createEquipment= (d) => api.post("/api/equipment/",          d);
export const updateEquipment= (id,d)=>api.put(`/api/equipment/${id}`,     d);
export const deleteEquipment= (id)=> api.delete(`/api/equipment/${id}`);
