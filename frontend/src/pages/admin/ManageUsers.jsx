import { useEffect, useState, useCallback } from "react";
import { listUsers, createUser, updateUser, deleteUser } from "../../api/adminApi";
import StatusBadge from "../../components/ui/StatusBadge";
import Modal from "../../components/ui/Modal";
import { Plus, Pencil, Trash2, Search } from "lucide-react";
import toast from "react-hot-toast";

const ROLES = ["student","faculty","admin","lab_assistant"];
const EMPTY = { name:"", email:"", password:"", role:"student", department:"", is_active:true };

export default function ManageUsers() {
  const [users,   setUsers]   = useState([]);
  const [total,   setTotal]   = useState(0);
  const [loading, setLoading] = useState(true);
  const [showForm,setShowForm]= useState(false);
  const [editing, setEditing] = useState(null);
  const [form,    setForm]    = useState(EMPTY);
  const [submitting,setSubmitting] = useState(false);
  const [deleting,  setDeleting]   = useState(null);
  const [search,  setSearch]  = useState("");
  const [roleFilter,setRoleFilter] = useState("");
  const [page,    setPage]    = useState(1);
  const LIMIT = 15;

  const fetchUsers = useCallback(() => {
    setLoading(true);
    const params = { per_page: LIMIT, page };
    if (search)     params.search = search;
    if (roleFilter) params.role   = roleFilter;
    listUsers(params)
      .then(({ data }) => { setUsers(data.items || []); setTotal(data.total || 0); })
      .catch(() => toast.error("Failed to load users"))
      .finally(() => setLoading(false));
  }, [search, roleFilter, page]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const openCreate = () => { setEditing(null); setForm(EMPTY); setShowForm(true); };
  const openEdit   = (u)  => {
    setEditing(u);
    setForm({ name:u.name||"", email:u.email||"", password:"", role:u.role||"student", department:u.department||"", is_active: u.is_active !== false });
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload = { ...form };
      if (!payload.password) delete payload.password;
      if (editing) {
        await updateUser(editing._id, payload);
        toast.success("User updated");
      } else {
        await createUser(payload);
        toast.success("User created");
      }
      setShowForm(false);
      fetchUsers();
    } catch (err) {
      toast.error(err?.response?.data?.error || "Save failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this user?")) return;
    setDeleting(id);
    try {
      await deleteUser(id);
      toast.success("User deleted");
      fetchUsers();
    } catch (err) {
      toast.error(err?.response?.data?.error || "Cannot delete user");
    } finally {
      setDeleting(null);
    }
  };

  const totalPages = Math.ceil(total / LIMIT);
  const f = (k) => (v) => setForm((p) => ({ ...p, [k]: v }));

  return (
    <div className="page-container">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Manage Users</h1>
          <p className="text-gray-500 text-sm">{total} registered users</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus size={16}/> Add User
        </button>
      </div>

      {/* Filters */}
      <div className="card mb-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[180px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
          <input placeholder="Search name or email…" className="input pl-9"
            value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}}/>
        </div>
        <select className="input min-w-[140px]" value={roleFilter}
          onChange={e=>{setRoleFilter(e.target.value);setPage(1);}}>
          <option value="">All Roles</option>
          {ROLES.map(r=><option key={r} value={r}>{r.replace("_"," ")}</option>)}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="space-y-2">{[...Array(6)].map((_,i)=><div key={i} className="card h-12 animate-pulse bg-gray-100"/>)}</div>
      ) : users.length === 0 ? (
        <div className="text-center py-16 text-gray-400">No users found.</div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["Name","Email","Role","Department","Active",""].map(h=>(
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {users.map((u) => (
                <tr key={u._id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800">{u.name}</td>
                  <td className="px-4 py-3 text-gray-500">{u.email}</td>
                  <td className="px-4 py-3"><span className="badge-purple capitalize">{u.role?.replace("_"," ")}</span></td>
                  <td className="px-4 py-3 text-gray-500">{u.department || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={u.is_active !== false ? "badge-green" : "badge-gray"}>
                      {u.is_active !== false ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right flex items-center justify-end gap-2">
                    <button onClick={()=>openEdit(u)} className="p-1.5 rounded hover:bg-blue-50 text-blue-600"><Pencil size={14}/></button>
                    <button onClick={()=>handleDelete(u._id)} disabled={deleting===u._id}
                      className="p-1.5 rounded hover:bg-red-50 text-red-600 disabled:opacity-40"><Trash2 size={14}/></button>
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
        title={editing ? "Edit User" : "Create User"}>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="label">Full Name <span className="text-red-500">*</span></label>
            <input className="input" required value={form.name} onChange={e=>f("name")(e.target.value)}/>
          </div>
          <div>
            <label className="label">Email <span className="text-red-500">*</span></label>
            <input type="email" className="input" required value={form.email} onChange={e=>f("email")(e.target.value)}/>
          </div>
          <div>
            <label className="label">{editing ? "New Password (leave blank to keep)" : "Password *"}</label>
            <input type="password" className="input" required={!editing} value={form.password} onChange={e=>f("password")(e.target.value)}/>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Role</label>
              <select className="input" value={form.role} onChange={e=>f("role")(e.target.value)}>
                {ROLES.map(r=><option key={r} value={r}>{r.replace("_"," ")}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Department</label>
              <input className="input" placeholder="e.g. Computer Science" value={form.department} onChange={e=>f("department")(e.target.value)}/>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="is_active" checked={form.is_active}
              onChange={e=>f("is_active")(e.target.checked)} className="rounded"/>
            <label htmlFor="is_active" className="text-sm text-gray-700">Active account</label>
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
