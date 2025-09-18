import React from "react";
import DashBoardLayout from "./layout";
import { useRouter } from "next/router";
import Dashboard from "./dashboard";
import Clusters from "./clusters";
import ModelRepo from "./modelRepo";
import Settings from "./settings";
import Chat from "./chat";
import ApiKeys from "./apiKeys";

const DashboardPage = () => {
  const router = useRouter();
  const renderDashboardContent = () => {
    switch (router.pathname) {
      case "/dashboard":
        return <Dashboard />;
      case "/clusters":
        return <Clusters />;
      case "/modelRepo":
        return <ModelRepo />;
      case "/settings":
        return <Settings />;
      case "/chat":
        return <Chat />;
      case "/apiKeys":
        return <ApiKeys />;
      // Add more cases for other dashboard pages as needed
      default:
        return null;
    }
  };
  return (
    <DashBoardLayout>
      {/* Add your dashboard page content here */}
      {/* <h2>Dashboard Page Content</h2> */}
      {renderDashboardContent()}
    </DashBoardLayout>
  );
};

export default DashboardPage;
