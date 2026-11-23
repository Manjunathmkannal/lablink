import { useEffect, useState, useCallback } from "react";
import { listBookings, cancelBooking } from "../../api/bookingApi";
import StatusBadge from "../../components/ui/StatusBadge";
import Modal from "../../components/ui/Modal";
import toast from "react-hot-toast";

export default function BookingHistory() {
  const [bookings, setBookings] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [cursor,   setCursor]   = useState(null);
  const [hasMore,  setHasMore]  = useState(false);
  const [filter,   setFilter]   = useState("all");
  const [selected, setSelected] = useState(null);  // for detail modal
  const [cancelling, setCancelling] = useState(null);

  const fetchBookings = useCallback((reset = false) => {
    setLoading(true);
    const params = {
      limit: 15,
      ...(filter !== "all" && { status: filter }),
      ...(cursor && !reset ? { after: cursor } : {}),
    };
    listBookings(params)
      .then(({ data }) => {
        const incoming = data.items || [];
        setBookings((prev) => reset ? incoming : [...prev, ...incoming]);
        setCursor(data.next_cursor || null);
        setHasMore(!!data.next_cursor);
      })
      .catch(() => toast.error("Failed to load bookings"))
      .finally(() => setLoading(false));
  }, [filter, cursor]);  // eslint-disable-line

  // Reset on filter change
  useEffect(() => {
    setCursor(null);
    fetchBookings(true);
  }, [filter]); // eslint-disable-line

  const handleCancel = async (id) => {
    setCancelling(id);
    try {
      await cancelBooking(id);
      toast.success("Booking cancelled");
      setBookings((prev) => prev.map((b) => b._id === id ? { ...b, status: "cancelled" } : b));
      setSelected(null);
    } catch (err) {
      toast.error(err?.response?.data?.error || "Cannot cancel booking");
    } finally {
      setCancelling(null);
    }
  };

  const STATUS_FILTERS = ["all", "pending", "approved", "rejected", "cancelled", "completed"];

  return (
    <div className="page-container">
      <h1 className="page-title mb-2">My Bookings</h1>
      <p className="text-gray-500 text-sm mb-6">Track and manage your equipment booking requests.</p>

      {/* Filter tabs */}
      <div className="flex flex-wrap gap-1 mb-5">
        {STATUS_FILTERS.map((s) => (
          <button key={s} onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium capitalize transition-colors ${
              filter === s ? "bg-primary text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}>{s}</button>
        ))}
      </div>

      {/* Table */}
      {loading && bookings.length === 0 ? (
        <div className="space-y-3">
          {[...Array(5)].map((_,i) => <div key={i} className="card h-16 animate-pulse bg-gray-100" />)}
        </div>
      ) : bookings.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p>No {filter !== "all" ? filter : ""} bookings found.</p>
        </div>
      ) : (
        <>
          <div className="card overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {["Equipment","Start","End","Purpose","Status",""].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {bookings.map((b) => (
                  <tr key={b._id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-800">{b.equipment_name || "—"}</td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {b.start_time ? new Date(b.start_time).toLocaleString(undefined,{dateStyle:"short",timeStyle:"short"}) : "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {b.end_time ? new Date(b.end_time).toLocaleString(undefined,{dateStyle:"short",timeStyle:"short"}) : "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 max-w-[180px] truncate">{b.purpose || "—"}</td>
                    <td className="px-4 py-3"><StatusBadge status={b.status} /></td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => setSelected(b)}
                        className="text-xs text-primary hover:underline mr-2">View</button>
                      {["pending","approved"].includes(b.status) && (
                        <button onClick={() => handleCancel(b._id)}
                          disabled={cancelling === b._id}
                          className="text-xs text-red-500 hover:underline disabled:opacity-40">
                          {cancelling === b._id ? "…" : "Cancel"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMore && (
            <div className="text-center mt-4">
              <button onClick={() => fetchBookings(false)} disabled={loading}
                className="btn-secondary text-sm">
                {loading ? "Loading…" : "Load More"}
              </button>
            </div>
          )}
        </>
      )}

      {/* Detail Modal */}
      <Modal isOpen={!!selected} onClose={() => setSelected(null)} title="Booking Details">
        {selected && (
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Status</span>
              <StatusBadge status={selected.status} />
            </div>
            <Row label="Equipment" value={selected.equipment_name || "—"} />
            <Row label="Start"     value={selected.start_time ? new Date(selected.start_time).toLocaleString() : "—"} />
            <Row label="End"       value={selected.end_time   ? new Date(selected.end_time).toLocaleString()   : "—"} />
            <Row label="Purpose"   value={selected.purpose    || "—"} />
            {selected.project_title && <Row label="Project" value={selected.project_title} />}
            {selected.approval_notes && (
              <div className="bg-yellow-50 rounded p-2 text-yellow-800 text-xs">
                <strong>Notes:</strong> {selected.approval_notes}
              </div>
            )}
            {["pending","approved"].includes(selected.status) && (
              <button onClick={() => handleCancel(selected._id)}
                disabled={cancelling === selected._id}
                className="btn-danger w-full mt-2 disabled:opacity-40">
                {cancelling === selected._id ? "Cancelling…" : "Cancel Booking"}
              </button>
            )}
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
