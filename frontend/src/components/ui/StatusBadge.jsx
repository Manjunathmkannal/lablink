// StatusBadge – maps booking/equipment status → Tailwind badge class
const MAP = {
  available: "badge-green",  pending: "badge-yellow",
  approved:  "badge-green",  rejected:"badge-red",
  cancelled: "badge-gray",   completed:"badge-blue",
  active:    "badge-purple", maintenance:"badge-yellow",
  retired:   "badge-gray",   booked:"badge-blue",
  draft:     "badge-gray",   submitted:"badge-yellow",
  under_review:"badge-yellow",good:"badge-green",
  fair:"badge-yellow",       poor:"badge-red",
};

export default function StatusBadge({ status }) {
  const cls = MAP[status] || "badge-gray";
  return <span className={cls}>{status?.replace("_"," ")}</span>;
}
