"use client";
import React from "react";
import dynamic from "next/dynamic";
import DashboardLayout from "@/components/layout/DashboardLayout";

// Dynamically import the iframe component to avoid SSR issues
const EmbeddedIframe = dynamic(() => import("./iFrame"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="text-bud-text-muted">Loading playground...</div>
    </div>
  ),
});

export default function PlaygroundPage() {
  return (
    <DashboardLayout>
      <div className="w-full h-full flex justify-center items-center overflow-hidden">
        <EmbeddedIframe />
      </div>
    </DashboardLayout>
  );
}
