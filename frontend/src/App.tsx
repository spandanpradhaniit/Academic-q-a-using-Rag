import { lazy, Suspense } from "react";
import { MotionConfig } from "framer-motion";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { WorkspaceLayout } from "./layouts/WorkspaceLayout";
import { AuthPage } from "./pages/AuthPage";
import { LandingPage } from "./pages/LandingPage";

const WorkspacePage = lazy(() =>
  import("./pages/WorkspacePage").then((module) => ({
    default: module.WorkspacePage,
  }))
);

function App() {
  return (
    <AuthProvider>
      <MotionConfig reducedMotion="user">
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<AuthPage mode="login" />} />
            <Route path="/register" element={<AuthPage mode="register" />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/app" element={<WorkspaceLayout />}>
                <Route
                  element={
                    <Suspense
                      fallback={
                        <div className="auth-loading" role="status">
                          <span className="spinner" /> Loading your workspace…
                        </div>
                      }
                    >
                      <Outlet />
                    </Suspense>
                  }
                >
                  <Route index element={<Navigate to="dashboard" replace />} />
                  <Route
                    path="dashboard"
                    element={<WorkspacePage page="dashboard" />}
                  />
                  <Route path="chat" element={<WorkspacePage page="chat" />} />
                  <Route
                    path="documents"
                    element={<WorkspacePage page="documents" />}
                  />
                  <Route
                    path="documents/:id"
                    element={<WorkspacePage page="document" />}
                  />
                  <Route
                    path="knowledge"
                    element={<WorkspacePage page="knowledge" />}
                  />
                  <Route
                    path="analytics"
                    element={<WorkspacePage page="analytics" />}
                  />
                  <Route
                    path="settings"
                    element={<WorkspacePage page="settings" />}
                  />
                  <Route
                    path="admin"
                    element={<WorkspacePage page="admin" />}
                  />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </MotionConfig>
    </AuthProvider>
  );
}

export default App;
