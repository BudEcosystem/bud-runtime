"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuthLayout from "@/components/auth/AuthLayout";
import { useAuthNavigation, useLoader } from "@/context/authContext";
import LoginForm from "@/components/auth/LoginForm";
import { motion, AnimatePresence } from "framer-motion";
import { useApiRequest } from "@/hooks/useApiRequest";
import { useEnvironment } from "@/components/providers/EnvironmentProvider";
import { useUser } from "@/stores/useUser";
import { successToast } from "@/components/toast";

interface DataInterface {
  email?: string;
  password?: string;
}

export default function Login() {
  const { activePage, setAuthError } = useAuthNavigation();
  const { showLoader, hideLoader } = useLoader();
  const router = useRouter();
  const [isBackToLogin, setIsBackToLogin] = useState(false);
  
  // Use the new environment system
  const environment = useEnvironment();
  const apiRequest = useApiRequest();

  useEffect(() => {
    console.log('Environment variables from provider:');
    console.log('tempApiBaseUrl:', environment.tempApiBaseUrl);
    console.log('baseUrl:', environment.baseUrl);
    console.log('novuBaseUrl:', environment.novuBaseUrl);
    
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
      const response = await apiRequest.Post("/auth/login", loginPayload);
      console.log("Login response:", response);

      if (response.data?.token) {
        // Store tokens
        localStorage.setItem("access_token", response.data.token.access_token);
        localStorage.setItem(
          "refresh_token",
          response.data.token.refresh_token,
        );

        setAuthError("");
        successToast("Login successful!");

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
        // For now, always redirect to /models regardless of reset password flags
        // Uncomment the condition below if you want to handle password reset
        // if (response.data.is_reset_password || response.data.first_login) {
        //   router.push("/auth/reset-password");
        // } else {
        //   router.push("/models");
        // }

        // Always go to models page after successful login
        router.push("/models");
      } else if (response.data) {
        // Handle case where login is successful but no token (shouldn't happen normally)
        setAuthError("");
        successToast("Login successful!");
        router.push("/models");
      }

      hideLoader();
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
            <>{activePage === 1 && <LoginForm onSubmit={handleLogin} />}</>
            {/* Other pages can be added here - reset password, contact admin, etc. */}
          </motion.div>
        </AnimatePresence>
      </div>
    </AuthLayout>
  );
}
