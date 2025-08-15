"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Check if user is authenticated
    const token = localStorage.getItem("access_token");

    if (token) {
      // If authenticated, redirect to models page
      router.push("/models");
    } else {
      // If not authenticated, redirect to login
      router.push("/login");
    }
  }, [router]);

  return (
    <div className="min-h-screen bg-bud-bg-primary flex items-center justify-center">
      <div className="animate-pulse">
        <div className="text-bud-text-primary">Loading...</div>
      </div>
    </div>
  );
}
