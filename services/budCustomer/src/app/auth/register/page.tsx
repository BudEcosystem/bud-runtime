"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuthLayout from "@/components/auth/AuthLayout";
import { useAuthNavigation, useLoader } from "@/context/authContext";
import RegisterForm from "@/components/auth/RegisterForm";
import LoginForm from "@/components/auth/LoginForm";
import { motion, AnimatePresence } from "framer-motion";

interface RegisterData {
  name: string;
  email: string;
  password: string;
  company: string;
  purpose: string;
  role: string;
}

export default function Register() {
  const { activePage, setActivePage, setAuthError, authError } = useAuthNavigation();
  const { isLoading, showLoader, hideLoader } = useLoader();
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
      // Mock registration logic - replace with your actual registration
      console.log("Registration attempt:", formData);

      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Mock success - replace with actual registration
      if (formData.email && formData.password) {
        // Store auth token or user data
        localStorage.setItem("auth_token", "mock_token");
        setAuthError('');

        // Redirect to dashboard
        router.push("/dashboard");
      }

      hideLoader();
    } catch (error: any) {
      console.error("Registration error:", error);
      setAuthError(error.message || "Registration failed. Please try again.");
      hideLoader();
    }
  };

  const handleLogin = async (payload: { email?: string; password?: string }) => {
    showLoader();
    try {
      // Mock authentication logic
      console.log("Login attempt:", payload);

      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Mock success
      if (payload.email && payload.password) {
        localStorage.setItem("auth_token", "mock_token");
        setAuthError('');
        router.push("/dashboard");
      }

      hideLoader();
    } catch (error: any) {
      console.error("Login error:", error);
      setAuthError(error.message || "Login failed. Please try again.");
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
              {activePage === 1 && <LoginForm onSubmit={handleLogin} />}
              {activePage === 2 && <RegisterForm onSubmit={handleRegister} />}
            </>
          </motion.div>
        </AnimatePresence>
      </div>
    </AuthLayout>
  );
}
