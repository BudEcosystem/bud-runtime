import React, { useEffect } from "react";
import { createPortal } from "react-dom";
import { useUseCases } from "src/stores/useUseCases";
import UseCaseIframe from "./UseCaseIframe";
import { X } from "lucide-react";

export default function UseCaseAppOverlay() {
  const { isAppOverlayOpen, selectedDeployment, closeAppOverlay } =
    useUseCases();

  useEffect(() => {
    if (!isAppOverlayOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeAppOverlay();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isAppOverlayOpen, closeAppOverlay]);

  if (!isAppOverlayOpen || !selectedDeployment) return null;

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 z-[1000]"
        onClick={closeAppOverlay}
      />
      {/* Overlay panel */}
      <div className="fixed inset-6 z-[1001] rounded-xl border border-white/10 overflow-hidden bg-[#0a0a0a] flex flex-col">
        <button
          onClick={closeAppOverlay}
          className="absolute top-3 right-3 z-10 p-1 rounded-md text-[#999] hover:text-white hover:bg-white/10 transition-colors"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>
        <UseCaseIframe
          deploymentId={selectedDeployment.id}
          className="w-full h-full"
        />
      </div>
    </>,
    document.body
  );
}
