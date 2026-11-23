import { useEffect, useState } from "react";
import { adminAnalytics } from "../../api/adminApi";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LineChart, Line,
} from "recharts";
import toast from "react-hot-toast";

const COLORS = ["#7c3aed","#2563eb","#059669","#d97706","#dc2626","#0891b2","#9333ea","#16a34a"];

export default function Analytics() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [months,  setMonths]  = useState(6);

  useEffect(() => {
    setLoading(true);
    adminAnalytics({ months })
      .then(({ data: d }) => setData(d))
      .catch(() => toast.error("Failed to load analytics"))
      .finally(() => setLoading(false));
  }, [months]);

  if (loading) return (
    <div className="page-container">
      <h1 className="page-title mb-6">Analytics</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[...Array(4)].map((_,i)=><div key={i} className="card h-64 animate-pulse bg-gray-100"/>)}
      </div>
    </div>
  );

  const utilization = data?.equipment_utilization || [];
  const deptUsage   = data?.department_usage      || [];
  const trends      = data?.monthly_trends        || [];
  const topEquip    = data?.top_equipment         || [];
  const userStats   = data?.user_stats            || [];
  const pending     = data?.pending_approvals     ?? 0;

  // Normalise monthly trends for Recharts
  const trendData = trends.map((t) => ({
    month: t._id ? `${t._id.year}-${String(t._id.month).padStart(2,"0")}` : "—",
    bookings: t.count || 0,
  }));

  return (
    <div className="page-container">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Analytics & Reports</h1>
          <p className="text-gray-500 text-sm">Equipment usage, booking trends and department insights.</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Trend months:</label>
          <select className="input w-24 text-sm" value={months} onChange={e=>setMonths(Number(e.target.value))}>
            {[3,6,12].map(m=><option key={m} value={m}>{m}mo</option>)}
          </select>
        </div>
      </div>

      {/* Top KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <KPI label="Pending Approvals" value={pending} accent={pending > 0 ? "text-yellow-600" : "text-green-600"}/>
        <KPI label="Equipment Items"   value={utilization.length}/>
        <KPI label="Departments"       value={deptUsage.length}/>
        <KPI label="Data Months"       value={months}/>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly trends */}
        <div className="card">
          <h2 className="text-sm font-semibold mb-4">Monthly Booking Trends</h2>
          {trendData.length === 0 ? <Empty/> : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={trendData} margin={{top:4,right:16,left:-10,bottom:0}}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0"/>
                <XAxis dataKey="month" tick={{fontSize:11}}/>
                <YAxis tick={{fontSize:11}} allowDecimals={false}/>
                <Tooltip/>
                <Line type="monotone" dataKey="bookings" stroke="#7c3aed" strokeWidth={2} dot={{r:4}}/>
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Equipment utilization pie */}
        <div className="card">
          <h2 className="text-sm font-semibold mb-4">Equipment Status Distribution</h2>
          {utilization.length === 0 ? <Empty/> : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={utilization} dataKey="count" nameKey="_id"
                  cx="50%" cy="50%" outerRadius={80} label={({_id,percent})=>`${_id} ${(percent*100).toFixed(0)}%`}>
                  {utilization.map((_,i)=><Cell key={i} fill={COLORS[i%COLORS.length]}/>)}
                </Pie>
                <Legend/>
                <Tooltip/>
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Department-wise bookings */}
        <div className="card">
          <h2 className="text-sm font-semibold mb-4">Bookings by Department</h2>
          {deptUsage.length === 0 ? <Empty/> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={deptUsage} margin={{top:4,right:16,left:-10,bottom:0}}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0"/>
                <XAxis dataKey="department_name" tick={{fontSize:10}} interval={0} angle={-15} textAnchor="end" height={40}/>
                <YAxis tick={{fontSize:11}} allowDecimals={false}/>
                <Tooltip/>
                <Bar dataKey="booking_count" fill="#2563eb" radius={[4,4,0,0]}/>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Top equipment */}
        <div className="card">
          <h2 className="text-sm font-semibold mb-4">Top 5 Most Booked Equipment</h2>
          {topEquip.length === 0 ? <Empty/> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={topEquip} layout="vertical" margin={{top:4,right:30,left:4,bottom:0}}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0"/>
                <XAxis type="number" tick={{fontSize:11}} allowDecimals={false}/>
                <YAxis type="category" dataKey="equipment_name" tick={{fontSize:11}} width={110}/>
                <Tooltip/>
                <Bar dataKey="booking_count" fill="#059669" radius={[0,4,4,0]}/>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* User stats */}
      {userStats.length > 0 && (
        <div className="card mt-6">
          <h2 className="text-sm font-semibold mb-4">Users by Role</h2>
          <div className="flex flex-wrap gap-4">
            {userStats.map((r) => (
              <div key={r._id} className="bg-purple-50 rounded-xl px-5 py-3 text-center">
                <p className="text-2xl font-bold text-primary">{r.count}</p>
                <p className="text-xs text-gray-500 capitalize mt-0.5">{r._id?.replace("_"," ")}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KPI({ label, value, accent = "text-gray-900" }) {
  return (
    <div className="card text-center py-4">
      <p className={`text-2xl font-bold ${accent}`}>{value ?? "—"}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  );
}

function Empty() {
  return <p className="text-sm text-gray-400 text-center py-8">No data available.</p>;
}
