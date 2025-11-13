"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useUser } from "@/stores/useUser";
import { useLoader } from "@/context/authContext";

interface AuthGuardProps {
  children: React.ReactNode;
}

// List of public routes that don't require authentication
const publicRoutes = ["/login", "/register", "/resetPassword", "/reset-password"];

export default function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, getUser, loadingUser } = useUser();
  const { showLoader, hideLoader } = useLoader();
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      // Check if current route is public
      const isPublicRoute = publicRoutes.some(
        (route) => pathname === route || pathname.startsWith(route),
      );

      // Check if we have access token
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("access_token")
          : null;

      // If on public route, allow access immediately
      if (isPublicRoute) {
        // If already authenticated and on login/register, redirect to models
        if (token && (pathname === "/login" || pathname === "/register")) {
          console.log("Already authenticated, redirecting to models");
          router.replace("/models");
        }
        setIsInitialized(true);
        return;
      }

      // If not on public route and no token, redirect to login
      if (!token) {
        console.log("No token found, redirecting to login");
        router.replace("/login");
        setIsInitialized(true);
        return;
      }

      // Always fetch user data on route change if token exists (like budadmin)
      if (token && !user?.id) {
        showLoader();
        try {
          const userData = await getUser();
          // Check if user needs to complete registration
          if (userData?.data?.result?.status === "invited") {
            console.log("User needs to complete registration");
            router.replace("/login");
            return;
          }
        } catch (error) {
          console.error("Failed to get user data:", error);
          // Redirect to login if user fetch fails
          router.replace("/login");
          return;
        } finally {
          hideLoader();
        }
      }

      setIsInitialized(true);
    };

    checkAuth();
  }, [pathname]); // Simplified dependency array - only re-run on pathname change

  // Show loading while initializing
  if (!isInitialized) {
    return (
      <div className="min-h-screen bg-bud-bg-primary flex items-center justify-center">
        <div className="animate-pulse">
          <div className="text-bud-text-primary">Loading...</div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
