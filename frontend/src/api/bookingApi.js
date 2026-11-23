import api from "./axiosInstance";
export const listBookings   = (p)   => api.get("/api/bookings/",           { params: p });
export const getBooking     = (id)  => api.get(`/api/bookings/${id}`);
export const createBooking  = (d)   => api.post("/api/bookings/",          d);
export const approveBooking = (id,d)=> api.put(`/api/bookings/${id}/approve`, d);
export const rejectBooking  = (id,d)=> api.put(`/api/bookings/${id}/reject`,  d);
export const cancelBooking  = (id)  => api.put(`/api/bookings/${id}/cancel`);
