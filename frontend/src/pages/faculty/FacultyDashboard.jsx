import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CheckSquare, CalendarDays, Clock, Users } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { listBookings } from "../../api/bookingApi";
import { listProjects } from "../../api/projectApi";
import StatCard from "../../components/ui/StatCard";
import StatusBadge from "../../components/ui/StatusBadge";
import toast from "react-hot-toast";

export default function FacultyDashboard() {
  const { user }  = useAuth();
  const [bookings,setBookings] = useState([]);
  const [projects,setProjects] = useState([]);
  const [loading, setLoading]  = useState(true);

  useEffect(() => {
    Promise.all([
      listBookings({ status: "pending", limit: 10 }),
      listProjects({ status: "submitted", limit: 10 }),
    ])
      .then(([b, p]) => {
        setBookings(b.data.items || []);
        setProjects(p.data.items || []);
      })
      .catch(() => toast.error("Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-container">
      <div className="mb-6">
        <h1 className="page-title">Faculty Dashboard</h1>
        <p className="text-gray-500 text-sm">Welcome, {user?.name}. Review pending approvals and upcoming schedules.</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {loading ? [...Array(4)].map((_,i)=><div key={i} className="card h-24 animate-pulse bg-gray-100"/>) : (
          <>
            <StatCard title="Pending Bookings"  value={bookings.length}  icon={CheckSquare} color="yellow" />
            <StatCard title="Projects to Review" value={projects.length} icon={Users}       color="purple" />
            <StatCard title="Today's Date"       value={new Date().toLocaleDateString()} icon={CalendarDays} color="blue" sub="Current" />
            <StatCard title="Total Pending"      value={bookings.length + projects.length} icon={Clock} color="red" />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending bookings */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold">Pending Booking Approvals</h2>
            <Link to="/faculty/approvals" className="text-xs text-primary hover:underline">View all</Link>
          </div>
          {loading ? <p className="text-sm text-gray-400">Loading…</p>
           : bookings.length === 0 ? <p className="text-sm text-gray-400">No pending bookings. 🎉</p>
           : (
            <div className="space-y-3">
              {bookings.slice(0,5).map((b) => (
                <div key={b._id} className="flex items-center justify-between border-b border-gray-50 pb-2 last:border-0">
                  <div>
                    <p className="text-sm font-medium">{b.student_name || b.user_name || "Student"}</p>
                    <p className="text-xs text-gray-400">{b.equipment_name || "Equipment"} · {b.start_time ? new Date(b.start_time).toLocaleDateString() : "—"}</p>
                  </div>
                  <StatusBadge status={b.status}/>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Projects to review */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold">Project Requests Awaiting Review</h2>
            <Link to="/faculty/approvals" className="text-xs text-primary hover:underline">View all</Link>
          </div>
          {loading ? <p className="text-sm text-gray-400">Loading…</p>
           : projects.length === 0 ? <p className="text-sm text-gray-400">No projects to review.</p>
           : (
            <div className="space-y-3">
              {projects.slice(0,5).map((p) => (
                <div key={p._id} className="flex items-center justify-between border-b border-gray-50 pb-2 last:border-0">
                  <div>
                    <p className="text-sm font-medium">{p.title}</p>
                    <p className="text-xs text-gray-400">
                      {p.student_name || "Student"} · Due: {p.deadline ? new Date(p.deadline).toLocaleDateString() : "—"}
                    </p>
                  </div>
                  <StatusBadge status={p.status}/>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
