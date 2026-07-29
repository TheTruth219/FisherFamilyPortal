import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import { ContentProvider } from "@/context/ContentContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Reunion from "@/pages/Reunion";
import FamilyBusiness from "@/pages/FamilyBusiness";
import Payments from "@/pages/Payments";
import Meetings from "@/pages/Meetings";
import Documents from "@/pages/Documents";
import Contact from "@/pages/Contact";

function Protected({ children }) {
  return (
    <ProtectedRoute>
      <ContentProvider>{children}</ContentProvider>
    </ProtectedRoute>
  );
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Toaster position="top-center" richColors />
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
            <Route path="/reunion" element={<Protected><Reunion /></Protected>} />
            <Route path="/family-business" element={<Protected><FamilyBusiness /></Protected>} />
            <Route path="/payments" element={<Protected><Payments /></Protected>} />
            <Route path="/meetings" element={<Protected><Meetings /></Protected>} />
            <Route path="/documents" element={<Protected><Documents /></Protected>} />
            <Route path="/contact" element={<Protected><Contact /></Protected>} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
