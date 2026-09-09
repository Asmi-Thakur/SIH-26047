/**
 * Route definitions for MediKiosk.
 *
 * Phase 1: every screen is a placeholder rendered inside the AppShell so the
 * navigation skeleton is real. Phase 2+ replaces individual page components.
 *
 * Layout:
 *   /            -> redirects to the patient Welcome screen
 *   /patient/*   -> patient kiosk flow (P01–P10 in docs/PROTOTYPE_BUILD_SPEC.md)
 *   /doctor/*    -> physician console (dashboard, triage, case view)
 */
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { CompletePage } from "../pages/patient/CompletePage";
import { ConsentPage } from "../pages/patient/ConsentPage";
import { DocumentsPage } from "../pages/patient/DocumentsPage";
import { IdentityPage } from "../pages/patient/IdentityPage";
import { InterviewPage } from "../pages/patient/InterviewPage";
import { ReviewPage } from "../pages/patient/ReviewPage";
import { WelcomePage } from "../pages/patient/WelcomePage";
import { CasePage } from "../pages/doctor/CasePage";
import { DashboardPage } from "../pages/doctor/DashboardPage";
import { TriagePage } from "../pages/doctor/TriagePage";

export const routes = [
  {
    path: "/",
    element: <Navigate to="/patient/welcome" replace />,
  },
  {
    element: <AppShell />,
    children: [
      {
        path: "/patient",
        element: <Navigate to="/patient/welcome" replace />,
      },
      { path: "/patient/welcome", element: <WelcomePage /> },
      { path: "/patient/identity", element: <IdentityPage /> },
      { path: "/patient/consent", element: <ConsentPage /> },
      { path: "/patient/interview", element: <InterviewPage /> },
      { path: "/patient/documents", element: <DocumentsPage /> },
      { path: "/patient/review", element: <ReviewPage /> },
      { path: "/patient/complete", element: <CompletePage /> },
      {
        path: "/doctor",
        element: <Navigate to="/doctor/dashboard" replace />,
      },
      { path: "/doctor/dashboard", element: <DashboardPage /> },
      { path: "/doctor/triage", element: <TriagePage /> },
      { path: "/doctor/case/:caseId", element: <CasePage /> },
    ],
  },
  { path: "*", element: <Navigate to="/patient/welcome" replace /> },
];

/** Browser router used by the app entrypoint. */
export const router = createBrowserRouter(routes);