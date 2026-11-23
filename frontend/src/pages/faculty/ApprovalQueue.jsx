import { useEffect, useState } from "react";
import { listBookings, approveBooking, rejectBooking } from "../../api/bookingApi";
import { listProjects, reviewProject } from "../../api/projectApi";
import StatusBadge from "../../components/ui/StatusBadge";
import Modal from "../../components/ui/Modal";
import toast from "react-hot-toast";
import { Check, X } from "lucide-react";

const TABS = ["bookings", "projects"];

export default function ApprovalQueue() {
  const [tab,       setTab]       = useState("bookings");
  const [bookings,  setBookings]  = useState([]);
  const [projects,  setProjects]  = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [selected,  setSelected]  = useState(null);
  const [noteModal, setNoteModal] = useState(null); // { type, item, action }
  const [notes,     setNotes]     = useState("");
  const [submitting,setSubmitting]= useState(false);

  const fetchAll = () => {
    setLoading(true);
    Promise.all([
      listBookings({ status: "pending", limit: 50 }),
      listProjects({ status: "submitted", limit: 50 }),
    ])
      .then(([b, p]) => {
        setBookings(b.data.items || []);
        setProjects(p.data.items || []);
      })
      .catch(() => toast.error("Failed to load queue"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchAll(); }, []);

  const openAction = (type, item, action) => {
    setNoteModal({ type, item, action });
    setNotes("");
  };

  const confirmAction = async () => {
    if (!noteModal) return;
    const { type, item, action } = noteModal;
    setSubmitting(true);
    try {
      if (type === "booking") {
        if (action === "approve") {
          await approveBooking(item._id, { notes });
          toast.success("Booking approved");
          setBookings((prev) => prev.filter((b) => b._id !== item._id));
        } else {
          if (!notes.trim()) { toast.error("Please provide a rejection reason"); setSubmitting(false); return; }
          await rejectBooking(item._id, { reason: notes });
          toast.success("Booking rejected");
          setBookings((prev) => prev.filter((b) => b._id !== item._id));
        }
      } else {
        // project
        await reviewProject(item._id, {
          decision: action === "approve" ? "approved" : "rejected",
          notes,
        });
        toast.success(`Project ${action}d`);
        setProjects((prev) => prev.filter((p) => p._id !== item._id));
      }
      setNoteModal(null);
      setSelected(null);
    } catch (err) {
      toast.error(err?.response?.data?.error || "Action failed");
    } finally {
      setSubmitting(false);
    }
  };

  const currentItems = tab === "bookings" ? bookings : projects;

  return (
    <div className="page-container">
      <h1 className="page-title mb-2">Approval Queue</h1>
      <p className="text-gray-500 text-sm mb-5">Review and act on student booking and project requests.</p>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-gray-100">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium capitalize border-b-2 transition-colors ${
              tab === t ? "border-primary text-primary" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {t === "bookings" ? `Bookings (${bookings.length})` : `Projects (${projects.length})`}
          </button>
        ))}
      </div>

      {/* List */}
      {loading ? (
        <div className="space-y-3">{[...Array(5)].map((_,i)=><div key={i} className="card h-16 animate-pulse bg-gray-100"/>)}</div>
      ) : currentItems.length === 0 ? (
        <div className="text-center py-16 text-gray-400">No pending {tab} — all clear! 🎉</div>
      ) : (
        <div className="space-y-3">
          {currentItems.map((item) => (
            <div key={item._id} className="card flex items-center justify-between gap-4">
              <div className="flex-1 min-w-0 cursor-pointer" onClick={() => setSelected({ ...item, _type: tab })}>
                {tab === "bookings" ? (
                  <>
                    <p className="text-sm font-semibold text-gray-800">{item.student_name || item.user_name || "Student"}</p>
                    <p className="text-xs text-gray-500">
                      {item.equipment_name || "Equipment"} ·{" "}
                      {item.start_time ? new Date(item.start_time).toLocaleString(undefined,{dateStyle:"medium",timeStyle:"short"}) : "—"}
                      {" "} → {item.end_time ? new Date(item.end_time).toLocaleString(undefined,{timeStyle:"short"}) : "—"}
                    </p>
                    {item.purpose && <p className="text-xs text-gray-400 mt-0.5 truncate">Purpose: {item.purpose}</p>}
                  </>
                ) : (
                  <>
                    <p className="text-sm font-semibold text-gray-800">{item.title}</p>
                    <p className="text-xs text-gray-500">
                      {item.student_name || "Student"} · Due: {item.deadline ? new Date(item.deadline).toLocaleDateString() : "—"}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5 line-clamp-1">{item.description}</p>
                  </>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button onClick={() => openAction(tab === "bookings" ? "booking" : "project", item, "approve")}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-green-50 text-green-700 text-xs font-medium hover:bg-green-100">
                  <Check size={14}/> Approve
                </button>
                <button onClick={() => openAction(tab === "bookings" ? "booking" : "project", item, "reject")}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-red-50 text-red-700 text-xs font-medium hover:bg-red-100">
                  <X size={14}/> Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail modal */}
      <Modal isOpen={!!selected} onClose={() => setSelected(null)} title="Request Details">
        {selected && (
          <div className="space-y-3 text-sm">
            {selected._type === "bookings" ? (
              <>
                <Row label="Student"   value={selected.student_name || selected.user_name || "—"}/>
                <Row label="Equipment" value={selected.equipment_name || "—"}/>
                <Row label="Start"     value={selected.start_time ? new Date(selected.start_time).toLocaleString() : "—"}/>
                <Row label="End"       value={selected.end_time   ? new Date(selected.end_time).toLocaleString()   : "—"}/>
                <Row label="Purpose"   value={selected.purpose    || "—"}/>
              </>
            ) : (
              <>
                <Row label="Student"  value={selected.student_name || "—"}/>
                <Row label="Title"    value={selected.title}/>
                <Row label="Deadline" value={selected.deadline ? new Date(selected.deadline).toLocaleDateString() : "—"}/>
                <div><p className="text-gray-500 mb-1">Description</p><p className="text-xs leading-relaxed">{selected.description}</p></div>
              </>
            )}
            <div className="flex gap-2 pt-2">
              <button onClick={() => { setSelected(null); openAction(selected._type === "bookings" ? "booking" : "project", selected, "approve"); }}
                className="btn-primary flex-1 text-sm">Approve</button>
              <button onClick={() => { setSelected(null); openAction(selected._type === "bookings" ? "booking" : "project", selected, "reject"); }}
                className="btn-danger flex-1 text-sm">Reject</button>
            </div>
          </div>
        )}
      </Modal>

      {/* Action confirmation modal */}
      <Modal isOpen={!!noteModal} onClose={() => setNoteModal(null)}
        title={noteModal?.action === "approve" ? "Confirm Approval" : "Confirm Rejection"}>
        {noteModal && (
          <div className="space-y-3">
            <p className="text-sm text-gray-600">
              {noteModal.action === "approve"
                ? "Add optional approval notes:"
                : "Please provide a reason for rejection:"}
            </p>
            <textarea className="input text-sm" rows={3}
              placeholder={noteModal.action === "approve" ? "Optional notes…" : "Rejection reason (required)…"}
              value={notes} onChange={(e) => setNotes(e.target.value)} />
            <div className="flex gap-2">
              <button onClick={() => setNoteModal(null)} className="btn-secondary flex-1">Cancel</button>
              <button onClick={confirmAction} disabled={submitting}
                className={`flex-1 disabled:opacity-50 ${noteModal.action === "approve" ? "btn-primary" : "btn-danger"}`}>
                {submitting ? "Processing…" : noteModal.action === "approve" ? "Confirm Approval" : "Confirm Rejection"}
              </button>
            </div>
          </div>
        )}
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
