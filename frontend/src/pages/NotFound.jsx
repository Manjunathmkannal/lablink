import { Link } from "react-router-dom";
import { FlaskConical } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 px-4">
      <FlaskConical size={48} className="text-primary mb-4" />
      <h1 className="text-5xl font-bold text-gray-800 mb-2">404</h1>
      <p className="text-gray-500 mb-6">Oops — that page doesn't exist.</p>
      <Link to="/" className="btn-primary">Go Home</Link>
    </div>
  );
}
