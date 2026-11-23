import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "http://localhost:5000",
  withCredentials: true,          // send HttpOnly refresh-token cookie
});

// Attach access token from localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh on 401
let _refreshing = false;
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    if (err.response?.status === 401 && !original._retry) {
      if (_refreshing) return Promise.reject(err);
      original._retry = true;
      _refreshing = true;
      try {
        const { data } = await axios.post(
          `${import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "http://localhost:5000"}/api/auth/refresh`,
          {},
          { withCredentials: true }
        );
        localStorage.setItem("access_token", data.access_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
      } finally {
        _refreshing = false;
      }
    }
    return Promise.reject(err);
  }
);

export default api;
