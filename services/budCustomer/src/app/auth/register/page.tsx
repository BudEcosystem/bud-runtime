"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuthLayout from "@/components/auth/AuthLayout";
import { useAuthNavigation, useLoader } from "@/context/authContext";
import RegisterForm from "@/components/auth/RegisterForm";
import LoginForm from "@/components/auth/LoginForm";
import { motion, AnimatePresence } from "framer-motion";
import { AppRequest } from "@/services/api/requests";
import { useUser } from "@/stores/useUser";
import { successToast } from "@/components/toast";

interface RegisterData {
  name: string;
  email: string;
  password: string;
  company: string;
  purpose: string;
  role: string;
}

export default function Register() {
  const { activePage, setActivePage, setAuthError, authError } =
    useAuthNavigation();
  const { isLoading, showLoader, hideLoader } = useLoader();
  const { getUser } = useUser();
  const router = useRouter();
  const [isBackToLogin, setIsBackToLogin] = useState(false);

  useEffect(() => {
    // Set active page to register (2) when component mounts
    setActivePage(2);
  }, [setActivePage]);

  useEffect(() => {
    if (activePage === 1) {
      setTimeout(() => {
        setIsBackToLogin(true);
      }, 500);
    } else {
      setTimeout(() => {
        setIsBackToLogin(false);
      }, 500);
    }
  }, [activePage]);

  const handleRegister = async (formData: { [key: string]: string }) => {
    showLoader();
    try {
      // Prepare the payload according to the API schema
      const payload = {
        name: formData.name,
        email: formData.email,
        password: formData.password,
        permissions: [
          {
            name: "model:view",
            has_permission: true,
          },
          {
            name: "project:view",
            has_permission: true,
          },
        ],
        role: "user", // Default role for new registrations
        company: formData.company,
        purpose: formData.purpose,
        user_type: "client",
      };

      console.log("Payload:", payload);

      // Make the API call
      const response = await AppRequest.Post("/auth/register", payload);
      console.log("Registration response:", response);
      if (response.data) {
        // Check if the response contains tokens
        if (response.data.token?.access_token) {
          // Store tokens
          localStorage.setItem(
            "access_token",
            response.data.token.access_token,
          );
          localStorage.setItem(
            "refresh_token",
            response.data.token.refresh_token,
          );

          setAuthError("");
          successToast("Registration successful!");

          // Redirect to projects or login based on response
          router.push("/projects");
        } else {
          // If no tokens, registration successful but needs to login
          setAuthError("");
          successToast("Registration successful! Please login.");
          setActivePage(1); // Switch to login page
        }
      }

      hideLoader();
    } catch (error: any) {
      console.error("Registration error:", error);
      const errorMessage =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "Registration failed. Please try again.";
      setAuthError(errorMessage);
      hideLoader();
    }
  };

  const handleLogin = async (payload: {
    email?: string;
    password?: string;
  }) => {
    console.log("=== LOGIN HANDLER CALLED ===");
    console.log("Login payload:", payload);
    showLoader();
    try {
      const response = await AppRequest.Post("/auth/login", payload);

      if (response.data?.token) {
        // Store tokens
        localStorage.setItem("access_token", response.data.token.access_token);
        localStorage.setItem(
          "refresh_token",
          response.data.token.refresh_token,
        );

        setAuthError("");

        // Get user data
        await getUser();

        // Handle different login scenarios
        if (response.data.is_reset_password || response.data.first_login) {
          router.push("/auth/reset-password");
        } else {
          router.push("/projects");
        }
      }

      hideLoader();
    } catch (error: any) {
      console.error("Login error:", error);
      const errorMessage =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "Login failed. Please try again.";
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
            <>
              {activePage === 1 && (
                <>
                  {console.log("Rendering LoginForm")}
                  <LoginForm onSubmit={handleLogin} />
                </>
              )}
              {activePage === 2 && (
                <>
                  {console.log("Rendering RegisterForm")}
                  <RegisterForm onSubmit={handleRegister} />
                </>
              )}
            </>
          </motion.div>
        </AnimatePresence>
      </div>
    </AuthLayout>
  );
}
