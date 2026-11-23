import api from "./axiosInstance";
export const aiRecommend = (d) => api.post("/api/ai/recommend", d);
export const aiSlots     = (d) => api.post("/api/ai/slots",     d);
export const aiDraft     = (d) => api.post("/api/ai/draft",     d);
export const aiStatus    = () => api.get("/api/ai/status");
