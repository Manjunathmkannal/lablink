import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Users, FlaskConical, CalendarDays, BarChart2, AlertCircle } from "lucide-react";
import { adminDashboard } from "../../api/adminApi";
import StatCard from "../../components/ui/StatCard";
import StatusBadge from "../../components/ui/StatusBadge";
import toast from "react-hot-toast";

export default function AdminDashboard() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminDashboard()
      .then(({ data: d }) => setData(d))
      .catch(() => toast.error("Failed to load admin dashboard"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-container">
      <div className="mb-6">
        <h1 className="page-title">Admin Dashboard</h1>
        <p className="text-gray-500 text-sm">System overview — users, equipment, bookings and pending actions.</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {loading ? (
          [...Array(4)].map((_,i)=><div key={i} className="card h-24 animate-pulse bg-gray-100"/>)
        ) : (
          <>
            <StatCard title="Total Users"      value={data?.total_users       ?? "—"} icon={Users}       color="purple"/>
            <StatCard title="Equipment Items"  value={data?.total_equipment   ?? "—"} icon={FlaskConical} color="blue"/>
            <StatCard title="Total Bookings"   value={data?.total_bookings    ?? "—"} icon={CalendarDays} color="green"/>
            <StatCard title="Pending Approvals"value={data?.pending_approvals ?? "—"} icon={AlertCircle}  color="yellow"
              sub={data?.pending_approvals > 0 ? "Action required" : "All clear"}/>
          </>
        )}
      </div>

      {/* Second row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {!loading && (
          <>
            <StatCard title="Students"       value={data?.students      ?? "—"} icon={Users} color="blue"/>
            <StatCard title="Faculty"        value={data?.faculty       ?? "—"} icon={Users} color="purple"/>
            <StatCard title="Lab Assistants" value={data?.lab_assistants?? "—"} icon={Users} color="green"/>
          </>
        )}
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { to: "/admin/users",     label: "Manage Users",     icon: Users,       color: "text-purple-600 bg-purple-50" },
          { to: "/admin/equipment", label: "Manage Equipment", icon: FlaskConical, color: "text-blue-600 bg-blue-50" },
          { to: "/admin/analytics", label: "Analytics",        icon: BarChart2,   color: "text-green-600 bg-green-50" },
          { to: "/admin/analytics", label: "Booking Reports",  icon: CalendarDays, color: "text-yellow-600 bg-yellow-50" },
        ].map(({ to, label, icon: Icon, color }) => (
          <Link key={label} to={to}
            className="card flex items-center gap-3 hover:border-primary transition-colors">
            <div className={`p-2 rounded-lg ${color}`}><Icon size={20}/></div>
            <span className="text-sm font-medium">{label}</span>
          </Link>
        ))}
      </div>

      {/* Recent bookings */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold">Recent Bookings</h2>
        </div>
        {loading ? <p className="text-sm text-gray-400">Loading…</p>
         : !data?.recent_bookings?.length ? <p className="text-sm text-gray-400">No bookings yet.</p>
         : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["Student","Equipment","Start","Status"].map(h=>(
                    <th key={h} className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.recent_bookings.map((b) => (
                  <tr key={b._id} className="hover:bg-gray-50">
                    <td className="px-3 py-2">{b.user_name || b.student_name || "—"}</td>
                    <td className="px-3 py-2">{b.equipment_name || "—"}</td>
                    <td className="px-3 py-2 whitespace-nowrap text-gray-500">
                      {b.start_time ? new Date(b.start_time).toLocaleString(undefined,{dateStyle:"short",timeStyle:"short"}) : "—"}
                    </td>
                    <td className="px-3 py-2"><StatusBadge status={b.status}/></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
