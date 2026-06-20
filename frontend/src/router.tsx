import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "./components/layout/app-layout";
import { AnalysisPage } from "./pages/analysis-page";
import { DashboardPage } from "./pages/dashboard-page";
import { NotFoundPage } from "./pages/not-found-page";
import { ReportDetailPage } from "./pages/report-detail-page";
import { ReportsPage } from "./pages/reports-page";
import { SettingsPage } from "./pages/settings-page";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    errorElement: <NotFoundPage />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "analysis", element: <AnalysisPage /> },
      { path: "reports", element: <ReportsPage /> },
      { path: "reports/:id", element: <ReportDetailPage /> },
    ],
  },
]);
