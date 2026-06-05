import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import ClinicianDashboard from './pages/ClinicianDashboard';
import { Activity } from 'lucide-react';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Activity className="animate-spin text-primary" size={32} />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

function AppRoutes() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center relative z-10">
        <Activity className="animate-spin text-primary" size={32} />
      </div>
    );
  }

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route 
          path="/login" 
          element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Login />} 
        />
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/clinician" 
          element={
            <ProtectedRoute>
              <ClinicianDashboard />
            </ProtectedRoute>
          } 
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AnimatePresence>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="relative min-h-screen w-full overflow-hidden bg-background">
          {/* Global Animated Background Layer */}
          <div className="fixed inset-0 z-0 pointer-events-none">
            <div className="absolute inset-0 mesh-bg opacity-70" />
            <div className="orb orb-1 top-[-10%] left-[-10%]" />
            <div className="orb orb-2 bottom-[-10%] right-[-10%]" />
            <div className="orb orb-3 top-[40%] left-[60%]" />
            <div className="absolute inset-0 noise-overlay" />
          </div>

          {/* Foreground Content */}
          <div className="relative z-10 w-full h-full">
            <AppRoutes />
          </div>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
