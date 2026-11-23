import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Search, Filter, Sparkles } from "lucide-react";
import { listEquipment } from "../../api/equipmentApi";
import { listDepartments } from "../../api/adminApi";
import StatusBadge from "../../components/ui/StatusBadge";
import AIAssistant from "../../components/ui/AIAssistant";
import toast from "react-hot-toast";

const STATUS_OPTIONS = ["", "available", "booked", "maintenance", "retired"];

export default function EquipmentBrowse() {
  const [items,       setItems]       = useState([]);
  const [depts,       setDepts]       = useState([]);
  const [total,       setTotal]       = useState(0);
  const [loading,     setLoading]     = useState(true);
  const [showAI,      setShowAI]      = useState(false);
  const [filters, setFilters] = useState({
    search: "", department_id: "", status: "", page: 1, limit: 12,
  });

  const fetchEquipment = useCallback(() => {
    setLoading(true);
    const { page, limit, ...rest } = filters;
    const params = { ...rest, page, per_page: limit };
    listEquipment(params)
      .then(({ data }) => { setItems(data.items || []); setTotal(data.total || 0); })
      .catch(() => toast.error("Failed to load equipment"))
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => {
    listDepartments().then(({ data }) => setDepts(data.items || [])).catch(() => {});
  }, []);

  useEffect(() => { fetchEquipment(); }, [fetchEquipment]);

  const setFilter = (key, value) => setFilters((f) => ({ ...f, [key]: value, page: 1 }));
  const totalPages = Math.ceil(total / filters.limit);

  return (
    <div className="page-container">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Browse Equipment</h1>
          <p className="text-gray-500 text-sm">{total} items found</p>
        </div>
        <button onClick={() => setShowAI(true)} className="btn-primary flex items-center gap-2">
          <Sparkles size={16} /> AI Suggest
        </button>
      </div>

      {/* Filters */}
      <div className="card mb-6">
        <div className="flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input placeholder="Search equipment…" className="input pl-9"
              value={filters.search}
              onChange={(e) => setFilter("search", e.target.value)} />
          </div>
          <select className="input min-w-[160px]" value={filters.department_id}
            onChange={(e) => setFilter("department_id", e.target.value)}>
            <option value="">All Departments</option>
            {depts.map((d) => <option key={d._id} value={d._id}>{d.name}</option>)}
          </select>
          <select className="input min-w-[140px]" value={filters.status}
            onChange={(e) => setFilter("status", e.target.value)}>
            {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s || "All Statuses"}</option>)}
          </select>
          <button onClick={() => setFilters({ search:"", department_id:"", status:"", page:1, limit:12 })}
            className="btn-secondary flex items-center gap-1 text-sm">
            <Filter size={14}/> Clear
          </button>
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {[...Array(8)].map((_,i) => <div key={i} className="card h-48 animate-pulse bg-gray-100" />)}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <FlaskConicalIcon size={40} className="mx-auto mb-3 opacity-30" />
          <p>No equipment matches your filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {items.map((item) => (
            <Link key={item._id} to={`/student/equipment/${item._id}`}
              className="card hover:border-primary transition-colors group">
              {/* Image placeholder */}
              <div className="h-28 rounded-lg bg-gradient-to-br from-purple-50 to-blue-50 flex items-center justify-center mb-3">
                <span className="text-3xl">🔬</span>
              </div>
              <StatusBadge status={item.status} />
              <h3 className="text-sm font-semibold text-gray-800 mt-2 group-hover:text-primary line-clamp-2">{item.name}</h3>
              <p className="text-xs text-gray-500 mt-1">{item.department_name || "—"}</p>
              <p className="text-xs text-gray-400 mt-1 truncate">{item.location || "—"}</p>
              {item.status === "available" && (
                <p className="text-xs text-green-600 font-medium mt-2">✓ Available to book</p>
              )}
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-6">
          <button disabled={filters.page === 1}
            onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}
            className="btn-secondary text-sm disabled:opacity-40">← Prev</button>
          <span className="text-sm text-gray-600 flex items-center px-3">
            Page {filters.page} of {totalPages}
          </span>
          <button disabled={filters.page >= totalPages}
            onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}
            className="btn-secondary text-sm disabled:opacity-40">Next →</button>
        </div>
      )}

      {showAI && <AIAssistant onClose={() => setShowAI(false)} />}
    </div>
  );
}

function FlaskConicalIcon({ size, className }) {
  return <svg width={size} height={size} className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 3h6M9 3v7L4 19a1 1 0 0 0 .9 1.5h14.2A1 1 0 0 0 20 19L15 10V3"/></svg>;
}
