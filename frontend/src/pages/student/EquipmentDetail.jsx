import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CalendarDays, MapPin, Info, Sparkles } from "lucide-react";
import { getEquipment, getAvailability } from "../../api/equipmentApi";
import { createBooking } from "../../api/bookingApi";
import { useAuth } from "../../context/AuthContext";
import StatusBadge from "../../components/ui/StatusBadge";
import Modal from "../../components/ui/Modal";
import AIAssistant from "../../components/ui/AIAssistant";
import toast from "react-hot-toast";

function toLocalDatetimeInput(date) {
  const d = new Date(date);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function todayPlusHours(h) {
  const d = new Date();
  d.setHours(d.getHours() + h, 0, 0, 0);
  return toLocalDatetimeInput(d);
}

export default function EquipmentDetail() {
  const { id }      = useParams();
  const navigate    = useNavigate();
  const { user }    = useAuth();
  const [equip,     setEquip]     = useState(null);
  const [slots,     setSlots]     = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [showBook,  setShowBook]  = useState(false);
  const [showAI,    setShowAI]    = useState(false);
  const [submitting,setSubmitting]= useState(false);
  const [form, setForm] = useState({
    start_time: todayPlusHours(1),
    end_time:   todayPlusHours(3),
    purpose: "",
    project_title: "",
  });

  useEffect(() => {
    setLoading(true);
    getEquipment(id)
      .then(({ data }) => setEquip(data))
      .catch(() => toast.error("Equipment not found"))
      .finally(() => setLoading(false));

    // Load this week's availability — backend accepts view + date params
    const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
    getAvailability(id, {
      view: "week",
      date: today,
    }).then(({ data }) => setSlots(data.bookings || [])).catch(() => {});
  }, [id]);

  const handleBook = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createBooking({
        equipment_id: id,
        start_time:   new Date(form.start_time).toISOString(),
        end_time:     new Date(form.end_time).toISOString(),
        purpose:      form.purpose,
        project_title: form.project_title || undefined,
      });
      toast.success("Booking submitted — awaiting approval");
      setShowBook(false);
      navigate("/student/bookings");
    } catch (err) {
      toast.error(err?.response?.data?.error || "Booking failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return (
    <div className="page-container flex items-center justify-center min-h-[400px]">
      <div className="animate-spin rounded-full h-10 w-10 border-4 border-primary border-t-transparent" />
    </div>
  );

  if (!equip) return (
    <div className="page-container text-center py-20 text-gray-400">Equipment not found.</div>
  );

  return (
    <div className="page-container">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-6">
        <ArrowLeft size={16}/> Back
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main info */}
        <div className="lg:col-span-2 space-y-4">
          <div className="card">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <StatusBadge status={equip.status} />
                  <span className="text-xs text-gray-400">{equip.category || "Equipment"}</span>
                </div>
                <h1 className="text-xl font-bold text-gray-900">{equip.name}</h1>
                <p className="text-sm text-gray-500 mt-1">{equip.model || ""} {equip.serial_number ? `· S/N: ${equip.serial_number}` : ""}</p>
              </div>
              <button onClick={() => setShowAI(true)}
                className="btn-secondary flex items-center gap-1.5 text-sm whitespace-nowrap">
                <Sparkles size={14}/> AI Help
              </button>
            </div>

            <p className="mt-4 text-sm text-gray-600 leading-relaxed">{equip.description || "No description provided."}</p>

            <div className="grid grid-cols-2 gap-4 mt-5">
              <div className="flex items-start gap-2">
                <MapPin size={16} className="text-gray-400 mt-0.5" />
                <div><p className="text-xs text-gray-400">Location</p><p className="text-sm font-medium">{equip.location || "—"}</p></div>
              </div>
              <div className="flex items-start gap-2">
                <Info size={16} className="text-gray-400 mt-0.5" />
                <div><p className="text-xs text-gray-400">Condition</p><p className="text-sm font-medium capitalize">{equip.condition || "—"}</p></div>
              </div>
            </div>
          </div>

          {/* Busy slots */}
          <div className="card">
            <h2 className="text-base font-semibold mb-3 flex items-center gap-2">
              <CalendarDays size={16} className="text-primary"/> Upcoming Busy Slots (7 days)
            </h2>
            {slots.length === 0 ? (
              <p className="text-sm text-green-600">✓ No bookings in the next 7 days — equipment is free!</p>
            ) : (
              <div className="space-y-2">
                {slots.map((s, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm bg-yellow-50 rounded-lg px-3 py-2">
                    <span className="text-yellow-600">⚠</span>
                    <span>{new Date(s.start).toLocaleString(undefined,{dateStyle:"medium",timeStyle:"short"})}</span>
                    <span className="text-gray-400">→</span>
                    <span>{new Date(s.end).toLocaleString(undefined,{dateStyle:"medium",timeStyle:"short"})}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Side booking panel */}
        <div className="card self-start">
          <h2 className="text-base font-semibold mb-4">Book this Equipment</h2>
          {equip.status !== "available" ? (
            <p className="text-sm text-red-500">This equipment is currently <strong>{equip.status}</strong> and cannot be booked.</p>
          ) : (
            <button onClick={() => setShowBook(true)} className="btn-primary w-full">
              Request Booking
            </button>
          )}
          <div className="mt-4 space-y-2 text-xs text-gray-400">
            <p>• Bookings require faculty approval</p>
            <p>• You'll be notified when approved</p>
            <p>• Cancel up to 1 hour before start</p>
          </div>
        </div>
      </div>

      {/* Booking Modal */}
      <Modal isOpen={showBook} onClose={() => setShowBook(false)} title="Book Equipment">
        <form onSubmit={handleBook} className="space-y-4">
          <div>
            <label className="label">Start Date & Time</label>
            <input type="datetime-local" className="input" required
              value={form.start_time} onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))} />
          </div>
          <div>
            <label className="label">End Date & Time</label>
            <input type="datetime-local" className="input" required
              value={form.end_time} onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value }))} />
          </div>
          <div>
            <label className="label">Purpose <span className="text-red-500">*</span></label>
            <input className="input" required placeholder="Why do you need this equipment?"
              value={form.purpose} onChange={(e) => setForm((f) => ({ ...f, purpose: e.target.value }))} />
          </div>
          <div>
            <label className="label">Project Title (optional)</label>
            <input className="input" placeholder="Related project name"
              value={form.project_title} onChange={(e) => setForm((f) => ({ ...f, project_title: e.target.value }))} />
          </div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={() => setShowBook(false)} className="btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={submitting} className="btn-primary flex-1 disabled:opacity-50">
              {submitting ? "Submitting…" : "Submit Request"}
            </button>
          </div>
        </form>
      </Modal>

      {showAI && <AIAssistant onClose={() => setShowAI(false)} />}
    </div>
  );
}
