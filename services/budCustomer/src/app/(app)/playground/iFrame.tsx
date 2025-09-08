"use client";
import { playGroundUrl, askBudModel, askBudUrl } from "@/config/environment";
import React, { useEffect, useRef, useState } from "react";

const EmbeddedIframe = ({ singleChat = false }: { singleChat?: boolean }) => {
  const [refreshToken, setRefreshToken] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const iframeRef = useRef<HTMLIFrameElement>(null);

  let iframeUrl = `${playGroundUrl}/login?embedded=true&refresh_token=${refreshToken}&is_single_chat=${singleChat}`;

  if (singleChat) {
    iframeUrl = `${playGroundUrl}/chat?embedded=true&refresh_token=${refreshToken}&is_single_chat=${singleChat}`;
    iframeUrl += `&model=${askBudModel}&base_url=${askBudUrl}&storage=ask-bud`;
  }

  useEffect(() => {
    if (typeof window !== "undefined") {
      const refresh = localStorage.getItem("refresh_token") || "";

      setRefreshToken(refresh);
      setIsLoading(false);

      // Inject custom styles to iframe
      const iframe = iframeRef.current;
      if (iframe && iframe.contentDocument) {
        try {
          const style = iframe.contentDocument.createElement("style");
          style.textContent = `
            body {
              background-color: transparent !important;
            }
            /* Additional CSS rules for iframe content */
          `;
          iframe.contentDocument.head.appendChild(style);
        } catch (e) {
          // Cross-origin restrictions may prevent style injection
          console.log("Unable to inject styles into iframe:", e);
        }
      }
    }
  }, []);

  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <div className="text-bud-text-muted">Loading playground...</div>
      </div>
    );
  }

  if (!refreshToken) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-bud-text-primary text-2xl font-bold mb-4">
            Access Denied
          </h1>
          <p className="text-bud-text-muted">
            Please login to access the playground.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full">
      <iframe
        ref={iframeRef}
        src={iframeUrl}
        className="w-full h-full border-0"
        title="Playground"
        allowFullScreen={false}
      />
    </div>
  );
};

export default EmbeddedIframe;
