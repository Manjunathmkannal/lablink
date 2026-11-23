import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import toast from "react-hot-toast";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const user = await login(form.email, form.password);
      const routes = { student: "/student/dashboard", faculty: "/faculty/dashboard",
                       admin: "/admin/dashboard", lab_assistant: "/lab/dashboard" };
      nav(routes[user.role] || "/student/dashboard", { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.error || "Login failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <span className="text-4xl">🔬</span>
          <h1 className="text-2xl font-bold text-gray-900 mt-2">LabLink</h1>
          <p className="text-sm text-gray-500 mt-1">Lab Resource Sharing Platform</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">Email</label>
            <input className="input-field" type="email" placeholder="you@college.edu"
              value={form.email} onChange={e=>setForm(p=>({...p, email: e.target.value}))} required/>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">Password</label>
            <input className="input-field" type="password" placeholder="••••••••"
              value={form.password} onChange={e=>setForm(p=>({...p, password: e.target.value}))} required/>
          </div>
          <button className="btn-primary w-full" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="text-center text-sm text-gray-500 mt-6">
          No account? <Link to="/register" className="text-primary font-medium hover:underline">Register</Link>
        </p>
      </div>
    </div>
  );
}
