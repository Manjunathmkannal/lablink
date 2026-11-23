import { NavLink } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import {
  LayoutDashboard, FlaskConical, CalendarDays, ClipboardList,
  CheckSquare, BarChart2, Users, Settings, LogOut, Wrench,
} from "lucide-react";

const NAV = {
  student: [
    { to: "/student/dashboard",  icon: LayoutDashboard, label: "Dashboard"      },
    { to: "/student/equipment",  icon: FlaskConical,    label: "Browse Equipment"},
    { to: "/student/bookings",   icon: CalendarDays,    label: "My Bookings"    },
    { to: "/student/projects",   icon: ClipboardList,   label: "Projects"       },
  ],
  faculty: [
    { to: "/faculty/dashboard",  icon: LayoutDashboard, label: "Dashboard"      },
    { to: "/faculty/approvals",  icon: CheckSquare,     label: "Approvals"      },
    { to: "/faculty/schedule",   icon: CalendarDays,    label: "Schedule"       },
  ],
  admin: [
    { to: "/admin/dashboard",    icon: LayoutDashboard, label: "Dashboard"      },
    { to: "/admin/equipment",    icon: FlaskConical,    label: "Equipment"      },
    { to: "/admin/users",        icon: Users,           label: "Users"          },
    { to: "/admin/analytics",    icon: BarChart2,       label: "Analytics"      },
  ],
  lab_assistant: [
    { to: "/lab/dashboard",      icon: LayoutDashboard, label: "Dashboard"      },
    { to: "/lab/handovers",      icon: Wrench,          label: "Handovers"      },
  ],
};

export default function Sidebar() {
  const { user, logout } = useAuth();
  const links = NAV[user?.role] || [];
  return (
    <aside className="w-64 min-h-screen bg-white border-r border-gray-200 flex flex-col">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-200">
        <span className="text-xl font-bold text-primary">🔬 LabLink</span>
        <p className="text-xs text-gray-500 mt-0.5 capitalize">{user?.role?.replace("_"," ")}</p>
      </div>
      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive ? "bg-primary-light text-primary" : "text-gray-600 hover:bg-gray-100"
              }`
            }>
            <Icon size={18}/> {label}
          </NavLink>
        ))}
      </nav>
      {/* User + logout */}
      <div className="px-4 py-4 border-t border-gray-200">
        <p className="text-xs font-medium text-gray-800 truncate">{user?.name}</p>
        <p className="text-xs text-gray-500 truncate">{user?.email}</p>
        <button onClick={logout}
          className="mt-2 flex items-center gap-2 text-xs text-red-600 hover:text-red-700">
          <LogOut size={14}/> Sign out
        </button>
      </div>
    </aside>
  );
}
