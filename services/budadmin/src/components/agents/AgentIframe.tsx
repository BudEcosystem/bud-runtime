import { playGroundUrl } from "@/components/environment";
import React, { useEffect, useRef, useState } from "react";

interface AgentIframeProps {
  sessionId?: string;
  promptIds?: string[];
}

const AgentIframe: React.FC<AgentIframeProps> = ({ sessionId, promptIds = [] }) => {
  const [refreshToken, setRefreshToken] = useState("");
  const playGroundUrl = "https://playground.dev.bud.studio";
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Build iframe URL for agent playground with promptIds
  const promptIdsParam = promptIds.filter(id => id).join(',');
  // const iframeUrl = `${playGroundUrl}/chat?embedded=true&refresh_token=${refreshToken}&is_single_chat=false${promptIdsParam ? `&promptIds=${promptIdsParam}` : ''}`;
  const iframeUrl = `http://localhost:3000/chat?embedded=true&refresh_token=${refreshToken}&agent_session=${sessionId || ''}${promptIdsParam ? `&promptIds=${promptIdsParam}` : ''}`;

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
