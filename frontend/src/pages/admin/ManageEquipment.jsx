import { useEffect, useState, useCallback } from "react";
import { listEquipment, createEquipment, updateEquipment, deleteEquipment } from "../../api/equipmentApi";
import { listDepartments, listLaboratories } from "../../api/adminApi";
import StatusBadge from "../../components/ui/StatusBadge";
import Modal from "../../components/ui/Modal";
import { Plus, Pencil, Trash2, Search } from "lucide-react";
import toast from "react-hot-toast";

const EMPTY = {
  name: "", description: "", category: "", model: "", serial_number: "",
  status: "available", condition: "good", location: "",
  department_id: "", laboratory_id: "",
};

export default function ManageEquipment() {
  const [items,   setItems]   = useState([]);
  const [depts,   setDepts]   = useState([]);
  const [labs,    setLabs]    = useState([]);
  const [total,   setTotal]   = useState(0);
  const [loading, setLoading] = useState(true);
  const [showForm,setShowForm]= useState(false);
  const [editing, setEditing] = useState(null);  // null = create, item = edit
  const [form,    setForm]    = useState(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [deleting,   setDeleting]   = useState(null);
  const [search,  setSearch]  = useState("");
  const [page,    setPage]    = useState(1);
  const LIMIT = 15;

  const fetchItems = useCallback(() => {
    setLoading(true);
    listEquipment({ search, per_page: LIMIT, page })
      .then(({ data }) => { setItems(data.items || []); setTotal(data.total || 0); })
      .catch(() => toast.error("Failed to load equipment"))
      .finally(() => setLoading(false));
  }, [search, page]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  useEffect(() => {
    listDepartments().then(({ data }) => setDepts(data.items || [])).catch(()=>{});
  }, []);

  const handleDeptChange = (deptId) => {
    setForm((f) => ({ ...f, department_id: deptId, laboratory_id: "" }));
    if (deptId) {
      listLaboratories({ department_id: deptId })
        .then(({ data }) => setLabs(data.items || []))
        .catch(()=>{});
    } else {
      setLabs([]);
    }
  };

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY);
    setLabs([]);
    setShowForm(true);
  };

  const openEdit = (item) => {
    setEditing(item);
    setForm({
      name: item.name||"", description: item.description||"",
      category: item.category||"", model: item.model||"",
      serial_number: item.serial_number||"",
      status: item.status||"available", condition: item.condition||"good",
      location: item.location||"",
      department_id: item.department_id||"", laboratory_id: item.laboratory_id||"",
    });
    if (item.department_id) {
      listLaboratories({ department_id: item.department_id })
        .then(({ data }) => setLabs(data.items || []))
        .catch(()=>{});
    }
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      if (editing) {
        await updateEquipment(editing._id, form);
        toast.success("Equipment updated");
      } else {
        await createEquipment(form);
        toast.success("Equipment created");
      }
      setShowForm(false);
      fetchItems();
    } catch (err) {
      toast.error(err?.response?.data?.error || "Save failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this equipment? This cannot be undone.")) return;
    setDeleting(id);
    try {
      await deleteEquipment(id);
      toast.success("Equipment deleted");
      fetchItems();
    } catch (err) {
      toast.error(err?.response?.data?.error || "Cannot delete — may have active bookings");
    } finally {
      setDeleting(null);
    }
  };

  const totalPages = Math.ceil(total / LIMIT);
  const f = (k) => (v) => setForm((prev) => ({ ...prev, [k]: v }));

  return (
    <div className="page-container">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Manage Equipment</h1>
          <p className="text-gray-500 text-sm">{total} items</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus size={16}/> Add Equipment
        </button>
      </div>

      {/* Search */}
      <div className="card mb-4">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
          <input placeholder="Search equipment…" className="input pl-9"
            value={search} onChange={(e)=>{ setSearch(e.target.value); setPage(1); }}/>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="space-y-2">{[...Array(6)].map((_,i)=><div key={i} className="card h-12 animate-pulse bg-gray-100"/>)}</div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-gray-400">No equipment found.</div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["Name","Category","Location","Status","Condition",""].map(h=>(
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {items.map((item) => (
                <tr key={item._id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800">{item.name}</td>
                  <td className="px-4 py-3 text-gray-500">{item.category || "—"}</td>
                  <td className="px-4 py-3 text-gray-500">{item.location || "—"}</td>
                  <td className="px-4 py-3"><StatusBadge status={item.status}/></td>
                  <td className="px-4 py-3"><StatusBadge status={item.condition}/></td>
                  <td className="px-4 py-3 text-right flex items-center justify-end gap-2">
                    <button onClick={()=>openEdit(item)}
                      className="p-1.5 rounded hover:bg-blue-50 text-blue-600"><Pencil size={14}/></button>
                    <button onClick={()=>handleDelete(item._id)}
                      disabled={deleting===item._id}
                      className="p-1.5 rounded hover:bg-red-50 text-red-600 disabled:opacity-40">
                      <Trash2 size={14}/>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <button disabled={page===1} onClick={()=>setPage(p=>p-1)} className="btn-secondary text-sm disabled:opacity-40">← Prev</button>
          <span className="flex items-center text-sm text-gray-600 px-2">Page {page} of {totalPages}</span>
          <button disabled={page>=totalPages} onClick={()=>setPage(p=>p+1)} className="btn-secondary text-sm disabled:opacity-40">Next →</button>
        </div>
      )}

      {/* Create / Edit Modal */}
      <Modal isOpen={showForm} onClose={()=>setShowForm(false)}
        title={editing ? "Edit Equipment" : "Add Equipment"}>
        <form onSubmit={handleSubmit} className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="label">Name <span className="text-red-500">*</span></label>
              <input className="input" required value={form.name} onChange={e=>f("name")(e.target.value)}/>
            </div>
            <div>
              <label className="label">Category</label>
              <input className="input" value={form.category} onChange={e=>f("category")(e.target.value)}/>
            </div>
            <div>
              <label className="label">Model</label>
              <input className="input" value={form.model} onChange={e=>f("model")(e.target.value)}/>
            </div>
            <div>
              <label className="label">Serial Number</label>
              <input className="input" value={form.serial_number} onChange={e=>f("serial_number")(e.target.value)}/>
            </div>
            <div>
              <label className="label">Location</label>
              <input className="input" value={form.location} onChange={e=>f("location")(e.target.value)}/>
            </div>
            <div>
              <label className="label">Status</label>
              <select className="input" value={form.status} onChange={e=>f("status")(e.target.value)}>
                {["available","booked","maintenance","retired"].map(s=><option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Condition</label>
              <select className="input" value={form.condition} onChange={e=>f("condition")(e.target.value)}>
                {["good","fair","poor"].map(c=><option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Department</label>
              <select className="input" value={form.department_id}
                onChange={e=>handleDeptChange(e.target.value)}>
                <option value="">Select dept…</option>
                {depts.map(d=><option key={d._id} value={d._id}>{d.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Laboratory</label>
              <select className="input" value={form.laboratory_id} onChange={e=>f("laboratory_id")(e.target.value)}>
                <option value="">Select lab…</option>
                {labs.map(l=><option key={l._id} value={l._id}>{l.name}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="label">Description</label>
              <textarea className="input" rows={2} value={form.description} onChange={e=>f("description")(e.target.value)}/>
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={()=>setShowForm(false)} className="btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={submitting} className="btn-primary flex-1 disabled:opacity-50">
              {submitting ? "Saving…" : editing ? "Update" : "Create"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
