import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import "./styles/index.css";
import { ThemeProvider } from "./lib/theme";
import AppShell from "./components/layout/AppShell";
import LoginPage from "./pages/Login";
import SignupPage from "./pages/Signup";
import PricingPage from "./pages/Pricing";
import LandingPage from "./pages/Landing";
import AcceptInvitePage from "./pages/AcceptInvite";
import ForgotPasswordPage from "./pages/ForgotPassword";
import ResetPasswordPage from "./pages/ResetPassword";
import DashboardPage from "./pages/Dashboard";
import AgentsPage from "./pages/Agents";
import AgentDetailPage from "./pages/AgentDetail";
import ToolsPage from "./pages/Tools";
import PoliciesPage from "./pages/Policies";
import PolicyEditorPage from "./pages/PolicyEditor";
import AuditPage from "./pages/Audit";
import BillingPage from "./pages/Billing";
import SettingsPage from "./pages/Settings";
import SsoSetupPage from "./pages/SsoSetup";
import ApprovalsPage from "./pages/Approvals";
import WebhooksPage from "./pages/Webhooks";
import GuardrailsPage from "./pages/Guardrails";
import RolesPage from "./pages/Roles";
import DocsPage from "./pages/Docs";
import NotFoundPage from "./pages/NotFound";
import HowItWorksPage from "./pages/HowItWorks";
import ProfilePage from "./pages/Profile";
import SuperAdminPage from "./pages/SuperAdmin";
import SsoCallbackPage from "./pages/SsoCallback";
import UsagePage from "./pages/Usage";
import RequireAuth from "./components/layout/RequireAuth";

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 5_000, retry: 1 } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={qc}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/docs" element={<DocsPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/invite" element={<AcceptInvitePage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            {/* SSO callback — must be outside RequireAuth, user has no token yet */}
            <Route path="/app/sso-callback" element={<SsoCallbackPage />} />
            <Route
              path="/app"
              element={
                <RequireAuth>
                  <AppShell />
                </RequireAuth>
              }
            >
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="agents" element={<AgentsPage />} />
              <Route path="agents/:id" element={<AgentDetailPage />} />
              <Route path="tools" element={<ToolsPage />} />
              <Route path="policies" element={<PoliciesPage />} />
              <Route path="policies/:id" element={<PolicyEditorPage />} />
              <Route path="policies/new" element={<PolicyEditorPage />} />
              <Route path="roles" element={<RolesPage />} />
              <Route path="how-it-works" element={<HowItWorksPage />} />
              <Route path="profile" element={<ProfilePage />} />
              <Route path="superadmin" element={<SuperAdminPage />} />
              <Route path="approvals" element={<ApprovalsPage />} />
              <Route path="webhooks" element={<WebhooksPage />} />
              <Route path="guardrails" element={<GuardrailsPage />} />
              <Route path="audit" element={<AuditPage />} />
              <Route path="billing" element={<BillingPage />} />
              <Route path="usage" element={<UsagePage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="settings/sso/new" element={<SsoSetupPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
