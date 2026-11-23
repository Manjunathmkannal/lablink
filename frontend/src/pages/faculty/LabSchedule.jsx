import { useEffect, useState } from "react";
import { listBookings } from "../../api/bookingApi";
import StatusBadge from "../../components/ui/StatusBadge";
import toast from "react-hot-toast";

const DAYS = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

function getWeekDates(offset = 0) {
  const now = new Date();
  const startOfWeek = new Date(now);
  startOfWeek.setDate(now.getDate() - now.getDay() + offset * 7);
  startOfWeek.setHours(0, 0, 0, 0);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startOfWeek);
    d.setDate(d.getDate() + i);
    return d;
  });
}

function formatHHMM(date) {
  return new Date(date).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export default function LabSchedule() {
  const [bookings, setBookings] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [weekOffset, setWeekOffset] = useState(0);

  const weekDates = getWeekDates(weekOffset);
  const weekStart = weekDates[0];
  const weekEnd   = weekDates[6];

  useEffect(() => {
    setLoading(true);
    const params = {
      status: "approved",
      limit:  100,
      // Note: backend may not filter by date range; we filter client-side
    };
    listBookings(params)
      .then(({ data }) => setBookings(data.items || []))
      .catch(() => toast.error("Failed to load schedule"))
      .finally(() => setLoading(false));
  }, [weekOffset]);

  // Filter bookings within the visible week
  const weekBookings = bookings.filter((b) => {
    if (!b.start_time) return false;
    const d = new Date(b.start_time);
    return d >= weekStart && d <= weekEnd;
  });

  // Group by day index (0=Sun … 6=Sat)
  const byDay = Array.from({ length: 7 }, () => []);
  weekBookings.forEach((b) => {
    const day = new Date(b.start_time).getDay();
    byDay[day].push(b);
  });

  return (
    <div className="page-container">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Lab Schedule</h1>
          <p className="text-gray-500 text-sm">
            {weekStart.toLocaleDateString(undefined,{month:"short",day:"numeric"})} –{" "}
            {weekEnd.toLocaleDateString(undefined,{month:"short",day:"numeric",year:"numeric"})}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setWeekOffset((w) => w - 1)} className="btn-secondary text-sm">← Prev</button>
          <button onClick={() => setWeekOffset(0)} className="btn-secondary text-sm">Today</button>
          <button onClick={() => setWeekOffset((w) => w + 1)} className="btn-secondary text-sm">Next →</button>
        </div>
      </div>

      {loading ? (
        <div className="card h-80 animate-pulse bg-gray-100"/>
      ) : (
        <div className="card overflow-hidden p-0">
          {/* Day headers */}
          <div className="grid grid-cols-7 border-b border-gray-100 bg-gray-50">
            {weekDates.map((d, i) => {
              const isToday = d.toDateString() === new Date().toDateString();
              return (
                <div key={i} className={`px-2 py-3 text-center ${isToday ? "bg-primary/10" : ""}`}>
                  <p className={`text-xs font-medium ${isToday ? "text-primary" : "text-gray-500"}`}>{DAYS[i]}</p>
                  <p className={`text-lg font-bold ${isToday ? "text-primary" : "text-gray-800"}`}>{d.getDate()}</p>
                </div>
              );
            })}
          </div>
          {/* Slots */}
          <div className="grid grid-cols-7 min-h-[400px] divide-x divide-gray-100">
            {byDay.map((daySlots, i) => (
              <div key={i} className="p-1.5 space-y-1.5">
                {daySlots.length === 0 ? (
                  <p className="text-xs text-gray-300 text-center mt-4">—</p>
                ) : (
                  daySlots.map((b, j) => (
                    <div key={j} className="rounded-md p-1.5 bg-purple-50 border-l-2 border-primary text-xs">
                      <p className="font-medium text-primary truncate">{b.equipment_name || "Equipment"}</p>
                      <p className="text-gray-500">
                        {formatHHMM(b.start_time)}–{formatHHMM(b.end_time)}
                      </p>
                      <p className="text-gray-400 truncate">{b.student_name || b.user_name || "Student"}</p>
                      <StatusBadge status={b.status}/>
                    </div>
                  ))
                )}
              </div>
            ))}
          </div>
          {weekBookings.length === 0 && (
            <p className="text-center text-sm text-gray-400 py-6">No approved bookings this week.</p>
          )}
        </div>
      )}

      {/* Summary */}
      <div className="mt-4 card">
        <h2 className="text-sm font-semibold mb-3">This Week Summary</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
          <div className="bg-purple-50 rounded-lg p-3">
            <p className="text-xl font-bold text-primary">{weekBookings.length}</p>
            <p className="text-xs text-gray-500">Approved Bookings</p>
          </div>
          <div className="bg-blue-50 rounded-lg p-3">
            <p className="text-xl font-bold text-blue-600">{new Set(weekBookings.map(b=>b.equipment_id)).size}</p>
            <p className="text-xs text-gray-500">Equipment Used</p>
          </div>
          <div className="bg-green-50 rounded-lg p-3">
            <p className="text-xl font-bold text-green-600">{new Set(weekBookings.map(b=>b.user_id)).size}</p>
            <p className="text-xs text-gray-500">Students Served</p>
          </div>
          <div className="bg-yellow-50 rounded-lg p-3">
            <p className="text-xl font-bold text-yellow-600">{weekDates.filter((_,i) => byDay[i].length > 0).length}</p>
            <p className="text-xs text-gray-500">Active Days</p>
          </div>
        </div>
      </div>
    </div>
  );
}
