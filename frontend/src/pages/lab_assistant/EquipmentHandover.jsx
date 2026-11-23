import { useEffect, useState } from "react";
import api from "../../api/axiosInstance";
import StatusBadge from "../../components/ui/StatusBadge";
import Modal from "../../components/ui/Modal";
import toast from "react-hot-toast";
import { CheckCircle, Wrench } from "lucide-react";

function listHandovers()           { return api.get("/api/lab/handovers"); }
function markReturn(id, d)         { return api.post(`/api/lab/handovers/${id}/return`, d); }
function listMaintenance()         { return api.get("/api/lab/maintenance"); }
function resolveMaintenance(id)    { return api.put(`/api/lab/maintenance/${id}/resolve`); }

const TABS = ["handovers","maintenance"];

export default function EquipmentHandover() {
  const [tab,         setTab]        = useState("handovers");
  const [handovers,   setHandovers]  = useState([]);
  const [maintenance, setMaintenance]= useState([]);
  const [loading,     setLoading]    = useState(true);
  const [returnModal, setReturnModal]= useState(null);
  const [condNote,    setCondNote]   = useState("");
  const [submitting,  setSubmitting] = useState(false);
  const [resolving,   setResolving]  = useState(null);

  const fetchAll = () => {
    setLoading(true);
    Promise.all([listHandovers(), listMaintenance()])
      .then(([h, m]) => {
        setHandovers(h.data.handovers || []);
        setMaintenance(m.data.maintenance_records || []);
      })
      .catch(() => toast.error("Failed to load handover data"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchAll(); }, []);

  const handleReturn = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await markReturn(returnModal._id, { condition_note: condNote || undefined });
      toast.success("Return recorded successfully");
      setHandovers((prev) => prev.filter((h) => h._id !== returnModal._id));
      setReturnModal(null);
      setCondNote("");
      fetchAll(); // refresh maintenance list too
    } catch (err) {
      toast.error(err?.response?.data?.error || "Return failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResolve = async (id) => {
    setResolving(id);
    try {
      await resolveMaintenance(id);
      toast.success("Maintenance resolved");
      setMaintenance((prev) => prev.filter((r) => r._id !== id));
    } catch (err) {
      toast.error(err?.response?.data?.error || "Resolve failed");
    } finally {
      setResolving(null);
    }
  };

  return (
    <div className="page-container">
      <h1 className="page-title mb-2">Handovers & Maintenance</h1>
      <p className="text-gray-500 text-sm mb-5">Track equipment currently handed out and open maintenance issues.</p>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="card flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-50"><CheckCircle size={20} className="text-blue-600"/></div>
          <div><p className="text-sm text-gray-500">Active Handouts</p><p className="text-2xl font-bold">{handovers.length}</p></div>
        </div>
        <div className="card flex items-center gap-3">
          <div className="p-2 rounded-lg bg-yellow-50"><Wrench size={20} className="text-yellow-600"/></div>
          <div><p className="text-sm text-gray-500">Open Issues</p><p className="text-2xl font-bold">{maintenance.length}</p></div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-100 mb-5">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium capitalize border-b-2 transition-colors ${
              tab === t ? "border-primary text-primary" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {t === "handovers" ? `Active Handouts (${handovers.length})` : `Maintenance (${maintenance.length})`}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">{[...Array(4)].map((_,i)=><div key={i} className="card h-16 animate-pulse bg-gray-100"/>)}</div>
      ) : tab === "handovers" ? (
        handovers.length === 0 ? (
          <div className="text-center py-16 text-gray-400">No active handouts. All equipment is accounted for.</div>
        ) : (
          <div className="card overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {["Equipment","Student","Start","End","Status",""].map(h=>(
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {handovers.map((h) => (
                  <tr key={h._id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-800">{h.equipment_name || "—"}</td>
                    <td className="px-4 py-3 text-gray-500">{h.student_name || h.user_name || "—"}</td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {h.start_time ? new Date(h.start_time).toLocaleString(undefined,{dateStyle:"short",timeStyle:"short"}) : "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {h.end_time ? new Date(h.end_time).toLocaleString(undefined,{dateStyle:"short",timeStyle:"short"}) : "—"}
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={h.status}/></td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => { setReturnModal(h); setCondNote(""); }}
                        className="btn-primary text-xs py-1 px-3">Mark Return</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : (
        maintenance.length === 0 ? (
          <div className="text-center py-16 text-gray-400">No open maintenance issues. 🎉</div>
        ) : (
          <div className="space-y-3">
            {maintenance.map((r) => (
              <div key={r._id} className="card flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="badge-yellow capitalize">{r.status}</span>
                    <span className="text-xs text-gray-400">
                      {r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-gray-800">{r.issue_description}</p>
                </div>
                <button onClick={() => handleResolve(r._id)} disabled={resolving === r._id}
                  className="btn-primary text-xs py-1 px-3 shrink-0 disabled:opacity-40">
                  {resolving === r._id ? "…" : "Resolve"}
                </button>
              </div>
            ))}
          </div>
        )
      )}

      {/* Return modal */}
      <Modal isOpen={!!returnModal} onClose={() => setReturnModal(null)} title="Record Equipment Return">
        {returnModal && (
          <form onSubmit={handleReturn} className="space-y-3">
            <div className="bg-blue-50 rounded-lg p-3 text-sm">
              <p className="font-medium text-blue-900">{returnModal.equipment_name || "Equipment"}</p>
              <p className="text-blue-700 text-xs mt-0.5">
                Borrowed by: {returnModal.student_name || returnModal.user_name || "—"}
              </p>
            </div>
            <div>
              <label className="label">Condition Note (optional)</label>
              <textarea className="input" rows={2}
                placeholder="Note any damage, wear, or issues observed on return…"
                value={condNote} onChange={e=>setCondNote(e.target.value)}/>
              <p className="text-xs text-gray-400 mt-1">A maintenance record will be created if you add a note.</p>
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={()=>setReturnModal(null)} className="btn-secondary flex-1">Cancel</button>
              <button type="submit" disabled={submitting} className="btn-primary flex-1 disabled:opacity-50">
                {submitting ? "Recording…" : "Confirm Return"}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
