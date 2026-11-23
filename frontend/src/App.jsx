import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";

// Auth pages
import Login    from "./pages/auth/Login";
import Register from "./pages/auth/Register";

// Layout
import ProtectedLayout from "./components/layout/ProtectedLayout";

// Student pages
import StudentDashboard from "./pages/student/StudentDashboard";
import EquipmentBrowse  from "./pages/student/EquipmentBrowse";
import EquipmentDetail  from "./pages/student/EquipmentDetail";
import BookingHistory   from "./pages/student/BookingHistory";
import ProjectRequests  from "./pages/student/ProjectRequests";

// Faculty pages
import FacultyDashboard from "./pages/faculty/FacultyDashboard";
import ApprovalQueue    from "./pages/faculty/ApprovalQueue";
import LabSchedule      from "./pages/faculty/LabSchedule";

// Admin pages
import AdminDashboard   from "./pages/admin/AdminDashboard";
import ManageEquipment  from "./pages/admin/ManageEquipment";
import ManageUsers      from "./pages/admin/ManageUsers";
import Analytics        from "./pages/admin/Analytics";

// Lab Assistant pages
import AssistantDashboard from "./pages/lab_assistant/AssistantDashboard";
import EquipmentHandover  from "./pages/lab_assistant/EquipmentHandover";

// Not found
import NotFound from "./pages/NotFound";

// Role-to-home mapping
const HOME = {
  student:       "/student/dashboard",
  faculty:       "/faculty/dashboard",
  admin:         "/admin/dashboard",
  lab_assistant: "/lab/dashboard",
};

function RoleRedirect() {
  const { user } = useAuth();
  return <Navigate to={HOME[user?.role] || "/login"} replace />;
}

function RequireRole({ roles, children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={HOME[user.role] || "/login"} replace />;
  return children;
}

export default function App() {
  const { loading } = useAuth();
  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-10 w-10 border-4 border-primary border-t-transparent" />
    </div>
  );

  return (
    <Routes>
      {/* Public */}
      <Route path="/login"    element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Protected shell */}
      <Route element={<ProtectedLayout />}>
        {/* Root → role home */}
        <Route index element={<RoleRedirect />} />

        {/* Student */}
        <Route path="/student" element={<RequireRole roles={["student"]}><RoleRedirect /></RequireRole>} />
        <Route path="/student/dashboard" element={<RequireRole roles={["student"]}><StudentDashboard /></RequireRole>} />
        <Route path="/student/equipment" element={<RequireRole roles={["student"]}><EquipmentBrowse /></RequireRole>} />
        <Route path="/student/equipment/:id" element={<RequireRole roles={["student"]}><EquipmentDetail /></RequireRole>} />
        <Route path="/student/bookings"  element={<RequireRole roles={["student"]}><BookingHistory /></RequireRole>} />
        <Route path="/student/projects"  element={<RequireRole roles={["student"]}><ProjectRequests /></RequireRole>} />

        {/* Faculty */}
        <Route path="/faculty" element={<RequireRole roles={["faculty"]}><RoleRedirect /></RequireRole>} />
        <Route path="/faculty/dashboard" element={<RequireRole roles={["faculty"]}><FacultyDashboard /></RequireRole>} />
        <Route path="/faculty/approvals" element={<RequireRole roles={["faculty"]}><ApprovalQueue /></RequireRole>} />
        <Route path="/faculty/schedule"  element={<RequireRole roles={["faculty"]}><LabSchedule /></RequireRole>} />

        {/* Admin */}
        <Route path="/admin" element={<RequireRole roles={["admin"]}><RoleRedirect /></RequireRole>} />
        <Route path="/admin/dashboard"  element={<RequireRole roles={["admin"]}><AdminDashboard /></RequireRole>} />
        <Route path="/admin/equipment"  element={<RequireRole roles={["admin"]}><ManageEquipment /></RequireRole>} />
        <Route path="/admin/users"      element={<RequireRole roles={["admin"]}><ManageUsers /></RequireRole>} />
        <Route path="/admin/analytics"  element={<RequireRole roles={["admin"]}><Analytics /></RequireRole>} />

        {/* Lab Assistant */}
        <Route path="/lab" element={<RequireRole roles={["lab_assistant"]}><RoleRedirect /></RequireRole>} />
        <Route path="/lab/dashboard" element={<RequireRole roles={["lab_assistant"]}><AssistantDashboard /></RequireRole>} />
        <Route path="/lab/handovers" element={<RequireRole roles={["lab_assistant"]}><EquipmentHandover /></RequireRole>} />
      </Route>

      {/* 404 */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
