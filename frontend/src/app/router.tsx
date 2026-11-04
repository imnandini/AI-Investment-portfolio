import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "./shell/AppLayout";
import { DashboardPage } from "../pages/Dashboard";
import { PortfolioPage } from "../pages/Portfolio";
import { ResearchPage } from "../pages/Research";
import { NotFoundPage } from "../pages/NotFound";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    errorElement: <NotFoundPage />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "portfolios", element: <PortfolioPage /> },
      { path: "research", element: <ResearchPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
