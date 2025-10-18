import { playGroundUrl } from "@/components/environment";
import React, { useEffect, useRef, useState } from "react";

interface AgentIframeProps {
  sessionId?: string;
  promptIds?: string[];
}

const AgentIframe: React.FC<AgentIframeProps> = ({ sessionId, promptIds = [] }) => {
  const [refreshToken, setRefreshToken] = useState("");
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Build iframe URL for agent playground with promptIds
  const promptIdsParam = promptIds.filter(id => id).join(',');
  // const iframeUrl = `http://localhost:8007/chat?embedded=true&refresh_token=${refreshToken}&agent_session=${sessionId || ''}${promptIdsParam ? `&promptIds=${promptIdsParam}` : ''}${promptIdsParam ? `?promptIds=${promptIdsParam}` : ''}`;
  const iframeUrl = `${playGroundUrl}/chat?embedded=true&refresh_token=${refreshToken}&agent_session=${sessionId || ''}${promptIdsParam ? `&promptIds=${promptIdsParam}` : ''}${promptIdsParam ? `?promptIds=${promptIdsParam}` : ''}`;

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

  if (!refreshToken) {
    return (
      <div className="flex items-center justify-center w-full h-full">
        <div className="text-center">
          <h1 className="text-[#EEEEEE] text-xl font-semibold mb-2">
            Access Denied
          </h1>
          <p className="text-[#808080] text-sm">
            Please login to access the agent playground.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full border-none">
      <iframe
        ref={iframeRef}
        src={iframeUrl}
        style={{ width: "100%", height: "100%", border: "none" }}
        title="Agent Playground"
        allowFullScreen={false}
      />
    </div>
  );
};

export default AgentIframe;
