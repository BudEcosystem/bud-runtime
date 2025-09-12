"use client";
import React, { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AuthLayout from "@/components/auth/AuthLayout";
import { useAuthNavigation, useLoader } from "@/context/authContext";
import LoginForm from "@/components/auth/LoginForm";
import { motion, AnimatePresence } from "framer-motion";
import { useApiRequest } from "@/hooks/useApiRequest";
import { useEnvironment } from "@/components/providers/EnvironmentProvider";
import { useUser } from "@/stores/useUser";
import { successToast, errorToast } from "@/components/toast";
import { AppRequest } from "@/services/api/requests";
import ContactAdmin from "../contactAdmin";

interface DataInterface {
  email?: string;
  password?: string;
}

function LoginContent() {
  const { activePage, setActivePage, setAuthError } = useAuthNavigation();
  const { showLoader, hideLoader } = useLoader();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isBackToLogin, setIsBackToLogin] = useState(false);
  const [oauthProcessing, setOauthProcessing] = useState(false);

  // Use the new environment system

  const environment = useEnvironment();
  const apiRequest = useApiRequest();

  // Handle OAuth callback
  useEffect(() => {
    const handleOAuthCallback = async () => {
      // Check for OAuth error parameters
      const error = searchParams.get("error");
      const errorDescription = searchParams.get("error_description");

      if (error) {
        AppRequest.OAuth.handleOAuthError(error, errorDescription || undefined);
        return;
      }

      // Check for OAuth success parameters
      const code = searchParams.get("code");
      const state = searchParams.get("state");
      const provider = searchParams.get("provider");
      const exchangeToken = searchParams.get("exchange_token");

      // Handle token exchange flow
      if (exchangeToken) {
        setOauthProcessing(true);
        showLoader();

        try {
          // Poll for token exchange completion
          const result =
            await AppRequest.OAuth.pollTokenExchange(exchangeToken);

          // Store tokens
          localStorage.setItem("access_token", result.access_token);
          if (result.refresh_token) {
            localStorage.setItem("refresh_token", result.refresh_token);
          }

          // Get user data
          try {
            const { getUser } = useUser.getState();
            await getUser();
          } catch (error) {
            console.log("Failed to get user data, continuing anyway:", error);
          }

          // Redirect to models page using window.location for clean redirect
          window.location.href = "/models";
        } catch (error: any) {
          console.error("OAuth token exchange error:", error);
          errorToast(
            error.message || "Authentication failed. Please try again.",
          );
        } finally {
          hideLoader();
          setOauthProcessing(false);
        }

        return;
      }

      // Handle authorization code flow (fallback)
      if (code && state && provider) {
        setOauthProcessing(true);
        showLoader();

        try {
          const result = await AppRequest.OAuth.handleCallback(
            provider,
            code,
            state,
          );

          // Store tokens
          localStorage.setItem("access_token", result.access_token);
          if (result.refresh_token) {
            localStorage.setItem("refresh_token", result.refresh_token);
          }

          // Get user data
          try {
            const { getUser } = useUser.getState();
            await getUser();
          } catch (error) {
            console.log("Failed to get user data, continuing anyway:", error);
          }

          // Redirect to models page using window.location for clean redirect
          window.location.href = "/models";
        } catch (error: any) {
          console.error("OAuth callback error:", error);
          errorToast(
            error.message || "Authentication failed. Please try again.",
          );
        } finally {
          hideLoader();
          setOauthProcessing(false);
        }
      }
    };

    if (searchParams) {
      handleOAuthCallback();
    }
  }, [searchParams, router, showLoader, hideLoader]);

  useEffect(() => {

    console.log("baseUrl:", environment.baseUrl);
    console.log("novuBaseUrl:", environment.novuBaseUrl);

    if (activePage === 4) {
      setTimeout(() => {
        setIsBackToLogin(true);
      }, 500);
    } else {
      setTimeout(() => {
        setIsBackToLogin(false);
      }, 500);
    }
  }, [activePage, environment]);

  const { getUser } = useUser();

  const handleLogin = async (payload: DataInterface) => {
    console.log("=== LOGIN HANDLER CALLED ===");
    console.log("Login payload:", payload);
    showLoader();
    try {
      // Prepare the payload
      const loginPayload = {
        email: payload.email,
        password: payload.password,
      };

      console.log("Calling API endpoint: /auth/login");
      console.log("Payload:", loginPayload);

      // Make the API call
      const response = await AppRequest.Post("/auth/login", loginPayload);
      console.log("Login response:", response);

      if (response.data?.token) {
        // Store tokens
        localStorage.setItem("access_token", response.data.token.access_token);
        localStorage.setItem(
          "refresh_token",
          response.data.token.refresh_token,
        );

        setAuthError("");

        // Get user data - commenting out for now as it causes 404 errors
        // TODO: Fix the /users/me endpoint or handle the error gracefully
        try {
          await getUser();
        } catch (error) {
          console.log("Failed to get user data, continuing anyway:", error);
        }

        // Log the response to debug
        console.log("Login response data:", {
          is_reset_password: response.data.is_reset_password,
          first_login: response.data.first_login,
        });

        // Handle different login scenarios
        hideLoader();

        if (response.data.is_reset_password) {
          router.replace("/auth/resetPassword");
        } else {
          // Use replace to avoid history stack issues and window.location for clean redirect
          window.location.href = "/models";
        }
      } else if (response.data) {
        // Handle case where login is successful but no token (shouldn't happen normally)
        setAuthError("");
        hideLoader();
        window.location.href = "/models";
      }
    } catch (error: any) {
      console.error("Login error:", error);
      const errorMessage =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "Login failed. Please check your credentials and try again.";
      setAuthError(errorMessage);
      hideLoader();
    }
  };
  const handleForgetPassword = async (email: string) => {
    showLoader();
    try {
      const response = await AppRequest.Post(`/users/reset-password`, {
        email,
      });
      if (response) {
        setActivePage(1);
      }
      console.log("response", response);
      successToast(response.data.message);
      hideLoader();
    } catch (error: any) {
      console.error("Reset password error:", error);
      const errorMessage =
        error?.response?.data?.detail ||
        error?.response?.data?.message ||
        "Failed to send reset email. Please try again.";
      errorToast(errorMessage);
      hideLoader();
    }
  };

  return (
    <AuthLayout>
      <div className="flex flex-col justify-center items-center h-full overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={activePage}
            initial={{ x: isBackToLogin ? -70 : 70, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: isBackToLogin ? 70 : -70, opacity: 0 }}
            transition={{ duration: 0.4, ease: "linear" }}
            className="w-[70%] h-full open-sans mt-[-1rem] flex justify-center items-center flex-col"
          >
            {oauthProcessing ? (
              <div className="flex flex-col items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-bud-purple"></div>
                <p className="mt-4 text-sm text-bud-text-muted">
                  Completing authentication...
                </p>
              </div>
            ) : (
              <>
                {activePage === 1 && <LoginForm onSubmit={handleLogin} />}
                {activePage === 4 && (
                  <ContactAdmin onSubmit={handleForgetPassword} />
                )}
                {/* Other pages can be added here - reset password, contact admin, etc. */}
              </>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </AuthLayout>
  );
}

export default function Login() {
  return (
    <Suspense
      fallback={
        <AuthLayout>
          <div className="flex flex-col justify-center items-center h-full">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-bud-purple"></div>
            <p className="mt-4 text-sm text-bud-text-muted">Loading...</p>
          </div>
        </AuthLayout>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
