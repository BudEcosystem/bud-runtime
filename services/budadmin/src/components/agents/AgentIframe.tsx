import { playGroundUrl } from "@/components/environment";
import React, { useEffect, useRef, useState } from "react";

interface AgentIframeProps {
  sessionId?: string;
  promptIds?: string[];
  typeFormMessage?: { timestamp: number; value: boolean } | null;
}

const AgentIframe: React.FC<AgentIframeProps> = ({ sessionId, promptIds = [], typeFormMessage = null }) => {
  const [refreshToken, setRefreshToken] = useState("");
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Build iframe URL for agent playground with promptIds (safe fallback if playGroundUrl is undefined)
  const promptIdsParam = promptIds.filter(id => id).join(',');
  const iframeUrl = playGroundUrl
    ? `${playGroundUrl}/chat?embedded=true&refresh_token=${refreshToken}&is_single_chat=false${promptIdsParam ? `&promptIds=${promptIdsParam}` : ''}`
    : '';

  useEffect(() => {
    if (typeof window !== "undefined") {
      setRefreshToken(localStorage.getItem("refresh_token") || "");
      const iframe = iframeRef.current;
      if (iframe && iframe.contentDocument) {
        const style = iframe.contentDocument.createElement("style");
        style.textContent = `
        body {
          background-color: #050505 !important;
        }
        /* Other CSS rules you want to inject */
      `;
        iframe.contentDocument.head.appendChild(style);
      }
    }
  }, []);

  // Send typeForm message to iframe when message changes
  useEffect(() => {
    if (typeFormMessage && iframeRef.current && iframeRef.current.contentWindow) {
      const message = {
        type: 'SET_TYPE_FORM',
        typeForm: typeFormMessage.value
      };

      // Send message to iframe with specific origin for security
      try {
        if (!playGroundUrl) {
          console.error('playGroundUrl is not defined. Check NEXT_PUBLIC_PLAYGROUND_URL environment variable.');
          return;
        }
        const targetOrigin = new URL(playGroundUrl).origin;
        iframeRef.current.contentWindow.postMessage(message, targetOrigin);
        console.log('Sent typeForm message to iframe:', message);
      } catch (error) {
        console.error('Failed to send message to iframe:', error);
      }
    }
  }, [typeFormMessage]);

  // Check if playGroundUrl is defined
  if (!playGroundUrl) {
    return (
      <div style={{ width: "100%", height: "100%", border: "none", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <h1 className="text-[#FF0000] text-2xl font-bold">
          Playground URL is not configured. Please set NEXT_PUBLIC_PLAYGROUND_URL environment variable.
        </h1>
      </div>
    );
  }

  if (!refreshToken) {
    return (
      <div style={{ width: "100%", height: "100%", border: "none" }}>
        <h1 className="text-[#000000] text-2xl font-bold">
          Access Denied. Please login to access the playground.
        </h1>
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: "100%", border: "none" }}>
      <iframe
        ref={iframeRef}
        src={iframeUrl}
        style={{ width: "100%", height: "100%", border: "none" }}
        title="AgentPlayground"
        allowFullScreen={false}
      />
    </div>
  );
};

export default AgentIframe;
