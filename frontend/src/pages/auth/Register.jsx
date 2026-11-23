import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { register } from "../../api/authApi";
import toast from "react-hot-toast";

export default function Register() {
  const nav = useNavigate();
  const [form, setForm] = useState({ name:"", email:"", password:"", role:"student", student_id:"" });
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await register(form);
      localStorage.setItem("access_token", data.access_token);
      const routes = { student:"/student/dashboard", faculty:"/faculty/dashboard",
                       admin:"/admin/dashboard", lab_assistant:"/lab/dashboard" };
      nav(routes[data.user.role] || "/student/dashboard", { replace: true });
    } catch (err) {
      const errs = err?.response?.data?.errors;
      toast.error(Array.isArray(errs) ? errs.join(", ") : (err?.response?.data?.error || "Registration failed"));
    } finally { setLoading(false); }
  };

  const f = (k) => (e) => setForm(p=>({...p, [k]: e.target.value}));

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
        <div className="text-center mb-6">
          <span className="text-4xl">🔬</span>
          <h1 className="text-2xl font-bold text-gray-900 mt-2">Create Account</h1>
        </div>
        <form onSubmit={submit} className="space-y-4">
          {[["Full Name","text","name","Your full name"],["Email","email","email","you@college.edu"],
            ["Password","password","password","min. 8 characters"]].map(([lbl,type,key,ph])=>(
            <div key={key}>
              <label className="text-sm font-medium text-gray-700 mb-1 block">{lbl}</label>
              <input className="input-field" type={type} placeholder={ph} value={form[key]} onChange={f(key)} required/>
            </div>
          ))}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">Role</label>
            <select className="input-field" value={form.role} onChange={f("role")}>
              {["student","faculty","lab_assistant"].map(r=>(
                <option key={r} value={r}>{r.replace("_"," ")}</option>
              ))}
            </select>
          </div>
          {form.role==="student" && (
            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">Student ID</label>
              <input className="input-field" placeholder="e.g. CS2021001" value={form.student_id} onChange={f("student_id")}/>
            </div>
          )}
          <button className="btn-primary w-full" disabled={loading}>{loading?"Creating…":"Create Account"}</button>
        </form>
        <p className="text-center text-sm text-gray-500 mt-6">
          Have an account? <Link to="/login" className="text-primary font-medium hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
