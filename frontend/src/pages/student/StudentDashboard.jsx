import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, FlaskConical, ClipboardList, Clock, Sparkles } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { listBookings } from "../../api/bookingApi";
import { listProjects } from "../../api/projectApi";
import StatCard from "../../components/ui/StatCard";
import StatusBadge from "../../components/ui/StatusBadge";
import AIAssistant from "../../components/ui/AIAssistant";
import toast from "react-hot-toast";

export default function StudentDashboard() {
  const { user } = useAuth();
  const [bookings,  setBookings]  = useState([]);
  const [projects,  setProjects]  = useState([]);
  const [showAI,    setShowAI]    = useState(false);
  const [loading,   setLoading]   = useState(true);

  useEffect(() => {
    Promise.all([listBookings({ limit: 5 }), listProjects({ limit: 5 })])
      .then(([b, p]) => {
        setBookings(b.data.items || []);
        setProjects(p.data.items || []);
      })
      .catch(() => toast.error("Failed to load dashboard data"))
      .finally(() => setLoading(false));
  }, []);

  const upcoming = bookings.filter((b) => ["pending", "approved"].includes(b.status));
  const pending  = projects.filter((p) => ["draft", "submitted", "under_review"].includes(p.status));

  return (
    <div className="page-container">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Welcome back, {user?.name?.split(" ")[0]} 👋</h1>
          <p className="text-gray-500 text-sm mt-0.5">Here's what's happening with your lab resources.</p>
        </div>
        <button onClick={() => setShowAI(true)}
          className="btn-primary flex items-center gap-2">
          <Sparkles size={16} /> AI Assistant
        </button>
      </div>

      {/* Stats row */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[...Array(4)].map((_, i) => <div key={i} className="card h-24 animate-pulse bg-gray-100" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard title="Total Bookings"    value={bookings.length}  icon={CalendarDays} color="purple" />
          <StatCard title="Upcoming"          value={upcoming.length}  icon={Clock}        color="blue"   />
          <StatCard title="Active Projects"   value={pending.length}   icon={ClipboardList} color="green" />
          <StatCard title="Equipment Access"  value={bookings.filter(b=>b.status==="approved").length} icon={FlaskConical} color="yellow" />
        </div>
      )}

      {/* Two-column lower section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent bookings */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-800">Recent Bookings</h2>
            <Link to="/student/bookings" className="text-xs text-primary hover:underline">View all</Link>
          </div>
          {loading ? <p className="text-sm text-gray-400">Loading…</p> : bookings.length === 0 ? (
            <p className="text-sm text-gray-400">No bookings yet. <Link to="/student/equipment" className="text-primary hover:underline">Browse equipment</Link></p>
          ) : (
            <div className="space-y-3">
              {bookings.slice(0,5).map((b) => (
                <div key={b._id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{b.equipment_name || "Equipment"}</p>
                    <p className="text-xs text-gray-400">
                      {b.start_time ? new Date(b.start_time).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—"}
                    </p>
                  </div>
                  <StatusBadge status={b.status} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent projects */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-800">Project Requests</h2>
            <Link to="/student/projects" className="text-xs text-primary hover:underline">View all</Link>
          </div>
          {loading ? <p className="text-sm text-gray-400">Loading…</p> : projects.length === 0 ? (
            <p className="text-sm text-gray-400">No project requests yet. <Link to="/student/projects" className="text-primary hover:underline">Create one</Link></p>
          ) : (
            <div className="space-y-3">
              {projects.slice(0,5).map((p) => (
                <div key={p._id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{p.title}</p>
                    <p className="text-xs text-gray-400">
                      Deadline: {p.deadline ? new Date(p.deadline).toLocaleDateString() : "—"}
                    </p>
                  </div>
                  <StatusBadge status={p.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick links */}
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Link to="/student/equipment" className="card flex items-center gap-3 hover:border-primary transition-colors">
          <div className="p-2 rounded-lg bg-purple-50"><FlaskConical size={20} className="text-primary" /></div>
          <div><p className="text-sm font-medium">Browse Equipment</p><p className="text-xs text-gray-400">Find available lab resources</p></div>
        </Link>
        <Link to="/student/bookings" className="card flex items-center gap-3 hover:border-primary transition-colors">
          <div className="p-2 rounded-lg bg-blue-50"><CalendarDays size={20} className="text-blue-600" /></div>
          <div><p className="text-sm font-medium">My Bookings</p><p className="text-xs text-gray-400">View and manage bookings</p></div>
        </Link>
        <Link to="/student/projects" className="card flex items-center gap-3 hover:border-primary transition-colors">
          <div className="p-2 rounded-lg bg-green-50"><ClipboardList size={20} className="text-green-600" /></div>
          <div><p className="text-sm font-medium">Projects</p><p className="text-xs text-gray-400">Submit equipment requests</p></div>
        </Link>
      </div>

      {showAI && <AIAssistant onClose={() => setShowAI(false)} />}
    </div>
  );
}
