import { createContext, useContext, useReducer, useEffect } from "react";
import { login as apiLogin, logout as apiLogout, getMe } from "../api/authApi";

const AuthContext = createContext(null);

const initialState = { user: null, loading: true, error: null };

function reducer(state, action) {
  switch (action.type) {
    case "SET_USER":    return { ...state, user: action.payload, loading: false, error: null };
    case "SET_LOADING": return { ...state, loading: action.payload };
    case "SET_ERROR":   return { ...state, error: action.payload, loading: false };
    case "LOGOUT":      return { ...initialState, loading: false };
    default:            return state;
  }
}

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  // Restore session on mount
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { dispatch({ type: "SET_LOADING", payload: false }); return; }
    getMe()
      .then(({ data }) => dispatch({ type: "SET_USER", payload: data }))
      .catch(() => { localStorage.removeItem("access_token"); dispatch({ type: "LOGOUT" }); });
  }, []);

  const login = async (email, password) => {
    dispatch({ type: "SET_LOADING", payload: true });
    const { data } = await apiLogin({ email, password });
    localStorage.setItem("access_token", data.access_token);
    dispatch({ type: "SET_USER", payload: data.user });
    return data.user;
  };

  const logout = async () => {
    try { await apiLogout(); } catch {}
    localStorage.removeItem("access_token");
    dispatch({ type: "LOGOUT" });
  };

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
