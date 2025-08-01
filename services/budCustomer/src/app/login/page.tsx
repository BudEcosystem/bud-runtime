"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuthLayout from "@/components/auth/AuthLayout";
import { useAuthNavigation, useLoader } from "@/context/authContext";
import LoginForm from "@/components/auth/LoginForm";
import { motion, AnimatePresence } from "framer-motion";

interface DataInterface {
  email?: string;
  password?: string;
}

export default function Login() {
  const { activePage, setAuthError, authError } = useAuthNavigation();
  const { showLoader, hideLoader } = useLoader();
  const router = useRouter();
  const [isBackToLogin, setIsBackToLogin] = useState(false);

  useEffect(() => {
    if (activePage === 4) {
      setTimeout(() => {
        setIsBackToLogin(true);
      }, 500);
    } else {
      setTimeout(() => {
        setIsBackToLogin(false);
      }, 500);
    }
  }, [activePage]);

  const handleLogin = async (payload: DataInterface) => {
    showLoader();
    try {
      // Mock authentication logic - replace with your actual authentication
      console.log("Login attempt:", payload);

      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Mock success - replace with actual authentication
      if (payload.email && payload.password) {
        // Store auth token or user data
        localStorage.setItem("auth_token", "mock_token");
        setAuthError('');

        // Redirect to dashboard
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
            </>
            {/* Other pages can be added here - reset password, contact admin, etc. */}
          </motion.div>
        </AnimatePresence>
      </div>
    </AuthLayout>
  );
}
