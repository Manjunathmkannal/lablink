import { Bell } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

export default function Navbar({ title = "" }) {
  const { user } = useAuth();
  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 flex-shrink-0">
      <h1 className="text-lg font-semibold text-gray-800">{title}</h1>
      <div className="flex items-center gap-3">
        <button className="relative p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg">
          <Bell size={18}/>
        </button>
        <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center text-sm font-medium">
          {user?.name?.[0]?.toUpperCase() || "?"}
        </div>
      </div>
    </header>
  );
}
