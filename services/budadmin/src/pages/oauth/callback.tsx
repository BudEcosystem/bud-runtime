import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { tempApiBaseUrl } from "@/components/environment";

type Status = "loading" | "success" | "error";

export default function OAuthCallbackPage() {
  const router = useRouter();
  const [status, setStatus] = useState<Status>("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    // Wait for router.query to be populated (Next.js hydration)
    if (!router.isReady) return;

    const { code, state } = router.query;

    if (!code || !state) {
      setStatus("error");
      setErrorMessage("Missing OAuth parameters (code or state).");
      return;
    }

    const codeStr = Array.isArray(code) ? code[0] : code;
    const stateStr = Array.isArray(state) ? state[0] : state;

    const params = new URLSearchParams({ code: codeStr, state: stateStr });

    fetch(`${tempApiBaseUrl}/connectors/oauth/public-callback?${params}`)
      .then(async (res) => {
        const data = await res.json();
        if (res.ok && data.success) {
          setStatus("success");
          // Auto-redirect to connections page after a short delay
          setTimeout(() => {
            router.replace("/settings/connections");
          }, 2000);
        } else {
          setStatus("error");
          setErrorMessage(data.message || "OAuth callback failed.");
        }
      })
      .catch((err) => {
        console.error("OAuth callback request failed:", err);
        setStatus("error");
        setErrorMessage("Network error — could not reach the server.");
      });
  }, [router.isReady, router.query]);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#0A0A0A",
        color: "#EEEEEE",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      <div
        style={{
          textAlign: "center",
          maxWidth: 400,
          padding: "2rem",
        }}
      >
        {status === "loading" && (
          <>
            <div style={{ marginBottom: "1.5rem" }}>
              <svg
                width="40"
                height="40"
                viewBox="0 0 40 40"
                style={{ animation: "spin 1s linear infinite" }}
              >
                <circle
                  cx="20"
                  cy="20"
                  r="16"
                  fill="none"
                  stroke="#965CDE"
                  strokeWidth="3"
                  strokeDasharray="80"
                  strokeDashoffset="20"
                  strokeLinecap="round"
                />
              </svg>
            </div>
            <h2
              style={{ fontSize: "1.125rem", fontWeight: 600, margin: "0 0 0.5rem" }}
            >
              Processing OAuth callback...
            </h2>
            <p style={{ fontSize: "0.875rem", color: "#757575", margin: 0 }}>
              Please wait while we complete the authorization.
            </p>
          </>
        )}

        {status === "success" && (
          <>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "50%",
                background: "rgba(34, 197, 94, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 1.5rem",
              }}
            >
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#22C55E"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <h2
              style={{ fontSize: "1.125rem", fontWeight: 600, margin: "0 0 0.5rem" }}
            >
              Authorization successful
            </h2>
            <p style={{ fontSize: "0.875rem", color: "#757575", margin: 0 }}>
              Redirecting you back to the app...
            </p>
          </>
        )}

        {status === "error" && (
          <>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "50%",
                background: "rgba(232, 46, 46, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 1.5rem",
              }}
            >
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#E82E2E"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M18 6L6 18" />
                <path d="M6 6l12 12" />
              </svg>
            </div>
            <h2
              style={{ fontSize: "1.125rem", fontWeight: 600, margin: "0 0 0.5rem" }}
            >
              Authorization failed
            </h2>
            <p
              style={{
                fontSize: "0.875rem",
                color: "#757575",
                margin: "0 0 1.5rem",
              }}
            >
              {errorMessage}
            </p>
            <a
              href="/settings/connections"
              style={{
                display: "inline-block",
                padding: "0.5rem 1.25rem",
                borderRadius: "0.375rem",
                background: "#965CDE",
                color: "#fff",
                fontSize: "0.875rem",
                fontWeight: 500,
                textDecoration: "none",
              }}
            >
              Back to Connections
            </a>
          </>
        )}
      </div>

      <style jsx>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
