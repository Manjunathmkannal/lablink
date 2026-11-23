import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { listEquipment, updateEquipment } from "../../api/equipmentApi";
import StatusBadge from "../../components/ui/StatusBadge";
import Modal from "../../components/ui/Modal";
import { Wrench, CheckCircle, AlertTriangle } from "lucide-react";
import toast from "react-hot-toast";

const STATUS_OPTIONS = ["available","maintenance","retired"];
const CONDITION_OPTIONS = ["good","fair","poor"];

export default function AssistantDashboard() {
  const { user }   = useAuth();
  const [items,    setItems]    = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [selected, setSelected] = useState(null);
  const [form,     setForm]     = useState({ status:"", condition:"", maintenance_notes:"" });
  const [submitting,setSubmitting] = useState(false);

  const fetchEquipment = () => {
    setLoading(true);
    listEquipment({ limit: 100 })
      .then(({ data }) => setItems(data.items || []))
      .catch(() => toast.error("Failed to load equipment"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchEquipment(); }, []);

  const openUpdate = (item) => {
    setSelected(item);
    setForm({ status: item.status||"available", condition: item.condition||"good", maintenance_notes:"" });
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await updateEquipment(selected._id, {
        status:    form.status,
        condition: form.condition,
        ...(form.maintenance_notes ? { maintenance_notes: form.maintenance_notes } : {}),
      });
      toast.success("Equipment status updated");
      setItems((prev) => prev.map((it) =>
        it._id === selected._id ? { ...it, status: form.status, condition: form.condition } : it
      ));
      setSelected(null);
    } catch (err) {
      toast.error(err?.response?.data?.error || "Update failed");
    } finally {
      setSubmitting(false);
    }
  };

  const available    = items.filter((i) => i.status === "available").length;
  const maintenance  = items.filter((i) => i.status === "maintenance").length;
  const poor         = items.filter((i) => i.condition === "poor").length;

  return (
    <div className="page-container">
      <div className="mb-6">
        <h1 className="page-title">Lab Assistant Dashboard</h1>
        <p className="text-gray-500 text-sm">Welcome, {user?.name}. Manage equipment status and condition.</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="card flex items-center gap-3">
          <div className="p-2 rounded-lg bg-green-50"><CheckCircle size={22} className="text-green-600"/></div>
          <div><p className="text-sm text-gray-500">Available</p><p className="text-2xl font-bold">{available}</p></div>
        </div>
        <div className="card flex items-center gap-3">
          <div className="p-2 rounded-lg bg-yellow-50"><Wrench size={22} className="text-yellow-600"/></div>
          <div><p className="text-sm text-gray-500">Under Maintenance</p><p className="text-2xl font-bold">{maintenance}</p></div>
        </div>
        <div className="card flex items-center gap-3">
          <div className="p-2 rounded-lg bg-red-50"><AlertTriangle size={22} className="text-red-600"/></div>
          <div><p className="text-sm text-gray-500">Poor Condition</p><p className="text-2xl font-bold">{poor}</p></div>
        </div>
      </div>

      {/* Equipment table */}
      {loading ? (
        <div className="space-y-2">{[...Array(5)].map((_,i)=><div key={i} className="card h-12 animate-pulse bg-gray-100"/>)}</div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["Equipment","Category","Location","Status","Condition",""].map(h=>(
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {items.map((item) => (
                <tr key={item._id} className={`hover:bg-gray-50 ${item.condition==="poor"?"bg-red-50/30":""}`}>
                  <td className="px-4 py-3 font-medium text-gray-800">{item.name}</td>
                  <td className="px-4 py-3 text-gray-500">{item.category||"—"}</td>
                  <td className="px-4 py-3 text-gray-500">{item.location||"—"}</td>
                  <td className="px-4 py-3"><StatusBadge status={item.status}/></td>
                  <td className="px-4 py-3"><StatusBadge status={item.condition}/></td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={()=>openUpdate(item)}
                      className="text-xs btn-secondary py-1 px-3">Update</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Update modal */}
      <Modal isOpen={!!selected} onClose={()=>setSelected(null)} title="Update Equipment Status">
        {selected && (
          <form onSubmit={handleUpdate} className="space-y-3">
            <p className="text-sm font-medium text-gray-800">{selected.name}</p>
            <div>
              <label className="label">Status</label>
              <select className="input" value={form.status} onChange={e=>setForm(f=>({...f,status:e.target.value}))}>
                {STATUS_OPTIONS.map(s=><option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Condition</label>
              <select className="input" value={form.condition} onChange={e=>setForm(f=>({...f,condition:e.target.value}))}>
                {CONDITION_OPTIONS.map(c=><option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Maintenance Notes (optional)</label>
              <textarea className="input" rows={2} placeholder="Describe any issues or maintenance performed…"
                value={form.maintenance_notes} onChange={e=>setForm(f=>({...f,maintenance_notes:e.target.value}))}/>
            </div>
            <div className="flex gap-2 pt-1">
              <button type="button" onClick={()=>setSelected(null)} className="btn-secondary flex-1">Cancel</button>
              <button type="submit" disabled={submitting} className="btn-primary flex-1 disabled:opacity-50">
                {submitting?"Saving…":"Save Changes"}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
