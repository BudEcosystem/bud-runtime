"use client";
import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "@/context/themeContext";
import styles from "./MainLayout.module.scss";

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const pathname = usePathname();
  const router = useRouter();
  const { effectiveTheme } = useTheme();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const menuItems = [
    { path: "/models", label: "Model Brochure", icon: "/icons/modelBig.png" },
    { path: "/playground", label: "Playground", icon: "/icons/playIcn.png" },
    { path: "/batches", label: "Batches", icon: "/icons/double.png" },
    { path: "/logs", label: "Logs", icon: "/icons/process.png" },
    { path: "/usage", label: "Usage", icon: "/icons/throughput.png" },
    { path: "/billing", label: "Billing", icon: "/icons/dollar.png" },
    { path: "/api-keys", label: "API Keys", icon: "/icons/key.png" },
    { path: "/projects", label: "Projects", icon: "/icons/project.png" },
  ];

  const handleLogout = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
    }
    router.push("/login");
  };

  return (
    <div className={styles.container}>
      {/* Sidebar */}
      <aside
        className={`${styles.sidebar} ${isSidebarCollapsed ? styles.collapsed : ""}`}
      >
        <div className={styles.logo}>
          <img
            src={
              effectiveTheme === "light"
                ? "/BudLogo-white.png"
                : "/images/BudLogo.png"
            }
            alt="Bud Logo"
          />
        </div>

        <nav className={styles.navigation}>
          {menuItems.map((item) => (
            <Link
              key={item.path}
              href={item.path}
              className={`${styles.navItem} ${pathname === item.path ? styles.active : ""}`}
            >
              <img src={item.icon} alt={item.label} className={styles.icon} />
              {!isSidebarCollapsed && <span>{item.label}</span>}
            </Link>
          ))}
        </nav>

        <div className={styles.footer}>
          <button onClick={handleLogout} className={styles.logoutBtn}>
            <img src="/icons/logout.png" alt="Logout" />
            {!isSidebarCollapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className={styles.main}>
        <header className={styles.header}>
          <button
            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            className={styles.toggleBtn}
          >
            ☰
          </button>

          <div className={styles.headerRight}>
            <button className={styles.notificationBtn}>
              <img src="/icons/notification.png" alt="Notifications" />
              <span className={styles.badge}>3</span>
            </button>

            <div className={styles.userInfo}>
              <img src="/icons/user.png" alt="User" />
              <span>demo@example.com</span>
            </div>
          </div>
        </header>

        <div className={styles.content}>{children}</div>
      </main>
    </div>
  );
};

export default MainLayout;
