import { useEffect, useState } from "react";
import { listProjects, createProject, submitProject } from "../../api/projectApi";
import { listEquipment } from "../../api/equipmentApi";
import { aiDraft } from "../../api/aiApi";
import StatusBadge from "../../components/ui/StatusBadge";
import Modal from "../../components/ui/Modal";
import { Plus, Sparkles, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

const EMPTY_FORM = {
  title: "", description: "", deadline: "",
  equipment_ids: [], department_id: "",
};

export default function ProjectRequests() {
  const [projects,  setProjects]  = useState([]);
  const [equipment, setEquipment] = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [showNew,   setShowNew]   = useState(false);
  const [selected,  setSelected]  = useState(null);
  const [form,      setForm]      = useState(EMPTY_FORM);
  const [submitting,setSubmitting]= useState(false);
  const [drafting,  setDrafting]  = useState(false);
  const [aiPrompt,  setAiPrompt]  = useState("");

  const fetchProjects = () => {
    setLoading(true);
    listProjects({ limit: 50 })
      .then(({ data }) => setProjects(data.items || []))
      .catch(() => toast.error("Failed to load projects"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchProjects();
    listEquipment({ limit: 100 }).then(({ data }) => setEquipment(data.items || [])).catch(() => {});
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const { data } = await createProject({
        ...form,
        deadline: form.deadline ? new Date(form.deadline).toISOString() : undefined,
      });
      toast.success("Project request created");
      setProjects((prev) => [data, ...prev]);
      setShowNew(false);
      setForm(EMPTY_FORM);
    } catch (err) {
      toast.error(err?.response?.data?.error || "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = async (id) => {
    try {
      const { data } = await submitProject(id);
      toast.success("Project submitted for review");
      setProjects((prev) => prev.map((p) => p._id === id ? { ...p, status: data.status || "submitted" } : p));
      setSelected(null);
    } catch (err) {
      toast.error(err?.response?.data?.error || "Failed to submit");
    }
  };

  const handleAIDraft = async () => {
    if (!aiPrompt.trim()) return;
    setDrafting(true);
    try {
      const { data } = await aiDraft({ description: aiPrompt });
      const draft = data.draft || "";
      // Try to populate form fields from AI suggestion
      if (draft) {
        const titleMatch = draft.match(/Title[:\s]+([^\n]+)/i);
        const descMatch  = draft.match(/Description[:\s]+([^\n]+(?:\n(?!Title|Equipment|Deadline)[^\n]+)*)/i);
        setForm((f) => ({
          ...f,
          title:       titleMatch?.[1]?.trim() || f.title,
          description: descMatch?.[1]?.trim()  || f.description,
        }));
        toast.success("AI draft applied — review and edit before submitting");
      }
    } catch {
      toast.error("AI draft failed");
    } finally {
      setDrafting(false);
    }
  };

  const toggleEquip = (id) => {
    setForm((f) => ({
      ...f,
      equipment_ids: f.equipment_ids.includes(id)
        ? f.equipment_ids.filter((x) => x !== id)
        : [...f.equipment_ids, id],
    }));
  };

  return (
    <div className="page-container">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Project Requests</h1>
          <p className="text-gray-500 text-sm">Submit project-based equipment access requests for faculty review.</p>
        </div>
        <button onClick={() => setShowNew(true)} className="btn-primary flex items-center gap-2">
          <Plus size={16}/> New Request
        </button>
      </div>

      {/* Projects list */}
      {loading ? (
        <div className="space-y-3">{[...Array(4)].map((_,i)=><div key={i} className="card h-20 animate-pulse bg-gray-100"/>)}</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p>No project requests yet.</p>
          <button onClick={() => setShowNew(true)} className="mt-3 btn-primary text-sm">Create your first request</button>
        </div>
      ) : (
        <div className="space-y-3">
          {projects.map((p) => (
            <div key={p._id} className="card flex items-center justify-between gap-4 cursor-pointer hover:border-primary transition-colors"
              onClick={() => setSelected(p)}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <StatusBadge status={p.status} />
                  <span className="text-xs text-gray-400">
                    {p.deadline ? `Due ${new Date(p.deadline).toLocaleDateString()}` : "No deadline"}
                  </span>
                </div>
                <h3 className="text-sm font-semibold text-gray-800 truncate">{p.title}</h3>
                <p className="text-xs text-gray-400 mt-0.5 line-clamp-1">{p.description}</p>
              </div>
              <div className="text-right shrink-0">
                {p.status === "draft" && (
                  <button onClick={(e) => { e.stopPropagation(); handleSubmit(p._id); }}
                    className="btn-primary text-xs py-1 px-3">Submit</button>
                )}
                {p.review_notes && <p className="text-xs text-yellow-600 mt-1 max-w-[160px]">Review: {p.review_notes}</p>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail Modal */}
      <Modal isOpen={!!selected} onClose={() => setSelected(null)} title="Project Details">
        {selected && (
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-gray-500">Status</span><StatusBadge status={selected.status}/>
            </div>
            <Row label="Title"       value={selected.title}/>
            <Row label="Deadline"    value={selected.deadline ? new Date(selected.deadline).toLocaleDateString() : "—"}/>
            <div>
              <span className="text-gray-500 block mb-1">Description</span>
              <p className="text-gray-800 leading-relaxed text-xs">{selected.description}</p>
            </div>
            {selected.review_notes && (
              <div className="bg-yellow-50 rounded p-2 text-yellow-800 text-xs">
                <strong>Faculty Notes:</strong> {selected.review_notes}
              </div>
            )}
            {selected.status === "draft" && (
              <button onClick={() => handleSubmit(selected._id)} className="btn-primary w-full mt-2">Submit for Review</button>
            )}
          </div>
        )}
      </Modal>

      {/* New project modal */}
      <Modal isOpen={showNew} onClose={() => { setShowNew(false); setForm(EMPTY_FORM); }} title="New Project Request">
        {/* AI Draft helper */}
        <div className="bg-purple-50 rounded-lg p-3 mb-4">
          <p className="text-xs font-medium text-purple-800 mb-2 flex items-center gap-1"><Sparkles size={12}/> AI Draft Helper</p>
          <div className="flex gap-2">
            <input className="input text-xs flex-1" placeholder="Briefly describe your project…"
              value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)} />
            <button type="button" onClick={handleAIDraft} disabled={drafting}
              className="btn-primary text-xs px-3 disabled:opacity-50">
              {drafting ? <Loader2 size={14} className="animate-spin"/> : "Draft"}
            </button>
          </div>
        </div>

        <form onSubmit={handleCreate} className="space-y-3">
          <div>
            <label className="label">Title <span className="text-red-500">*</span></label>
            <input className="input" required value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
          </div>
          <div>
            <label className="label">Description <span className="text-red-500">*</span></label>
            <textarea className="input" rows={3} required value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          </div>
          <div>
            <label className="label">Deadline</label>
            <input type="date" className="input" value={form.deadline}
              onChange={(e) => setForm((f) => ({ ...f, deadline: e.target.value }))} />
          </div>
          <div>
            <label className="label">Required Equipment (select multiple)</label>
            <div className="max-h-36 overflow-y-auto border border-gray-200 rounded-lg p-2 space-y-1">
              {equipment.length === 0 && <p className="text-xs text-gray-400">Loading…</p>}
              {equipment.map((e) => (
                <label key={e._id} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-gray-50 p-1 rounded">
                  <input type="checkbox" checked={form.equipment_ids.includes(e._id)}
                    onChange={() => toggleEquip(e._id)} className="rounded" />
                  <span>{e.name}</span>
                  <StatusBadge status={e.status}/>
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={() => { setShowNew(false); setForm(EMPTY_FORM); }} className="btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={submitting} className="btn-primary flex-1 disabled:opacity-50">
              {submitting ? "Creating…" : "Create Draft"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-gray-500 shrink-0">{label}</span>
      <span className="text-gray-800 text-right">{value}</span>
    </div>
  );
}
