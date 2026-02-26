/**
 * UseCaseIframe - Embeds the deployed use case web UI inside budadmin.
 *
 * Follows the same auth-token and iframe pattern used by:
 *   - src/pages/home/playground/iFrame.tsx  (playground embed)
 *   - src/components/agents/AgentIframe.tsx  (agent embed)
 *
 * The iframe points at budapp's internal reverse proxy endpoint which
 * forwards the request through Envoy Gateway to the use case service
 * running on the target cluster.
 */

import React, { useCallback, useEffect, useState } from "react";
import { apiBaseUrl, usecaseDomain } from "@/components/environment";
import { DeploymentAPI } from "@/lib/budusecases";
import { successToast, errorToast } from "@/components/toast";

interface UseCaseIframeProps {
  /** The use-case deployment ID */
  deploymentId: string;
  /** Optional extra CSS class for the wrapper */
  className?: string;
}

const UseCaseIframe: React.FC<UseCaseIframeProps> = ({
  deploymentId,
  className,
}) => {
  const [accessToken, setAccessToken] = useState("");
  const [gatewayError, setGatewayError] = useState(false);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setAccessToken(localStorage.getItem("access_token") || "");
    }
  }, []);

  // Build URL: prefer subdomain (no HTML rewriting needed), fall back to path-based proxy
  const iframeUrl = accessToken
    ? usecaseDomain
      ? `https://uc-${deploymentId}.${usecaseDomain}/?token=${accessToken}`
      : `${apiBaseUrl}/budusecases/usecases/${deploymentId}/ui/?token=${accessToken}`
    : "";

  // Check if the iframe URL is accessible (detect 503 gateway errors)
  useEffect(() => {
    if (!iframeUrl) return;
    fetch(iframeUrl, { method: "GET", redirect: "follow" })
      .then((res) => {
        if (res.status === 503) {
          setGatewayError(true);
        }
      })
      .catch(() => {
        // Network error — let the iframe handle it
      });
  }, [iframeUrl]);

  const handleRetryGateway = useCallback(async () => {
    setRetrying(true);
    try {
      await DeploymentAPI.retryGateway(deploymentId);
      successToast("Gateway route created. Reloading...");
      setGatewayError(false);
      // Small delay to let the route propagate before reloading the iframe
      setTimeout(() => {
        setAccessToken("");
        setTimeout(() => {
          setAccessToken(localStorage.getItem("access_token") || "");
        }, 100);
      }, 2000);
    } catch (err: any) {
      const msg = err?.response?.data?.message || err?.message || "Failed to create gateway route";
      errorToast(msg);
    } finally {
      setRetrying(false);
    }
  }, [deploymentId]);

  if (!accessToken) {
    return (
      <div
        className={
          className ||
          "w-full h-full flex items-center justify-center"
        }
      >
        <span className="text-[#757575] text-sm">
          Access Denied. Please log in to view this use case.
        </span>
      </div>
    );
  }

  if (gatewayError) {
    return (
      <div
        className={
          className ||
          "w-full h-full flex items-center justify-center"
        }
      >
        <div className="flex flex-col items-center gap-4 max-w-md text-center">
          <span className="text-[#B3B3B3] text-sm">
            Gateway route is not available for this deployment.
            The route may not have been created during deployment.
          </span>
          <button
            onClick={handleRetryGateway}
            disabled={retrying}
            className="px-4 py-2 bg-[#965CDE] text-white text-sm rounded-md hover:bg-[#7D4BC2] disabled:opacity-50 transition-colors"
          >
            {retrying ? "Creating Route..." : "Retry Gateway Route"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={className || "w-full h-full"}>
      <iframe
        src={iframeUrl}
        style={{ width: "100%", height: "100%", border: "none" }}
        title="Use Case UI"
        allow="clipboard-write; clipboard-read"
        allowFullScreen={false}
      />
    </div>
  );
};

export default UseCaseIframe;
