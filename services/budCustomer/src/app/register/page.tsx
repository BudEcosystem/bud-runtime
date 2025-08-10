"use client";
import React from "react";
import { useRouter } from "next/navigation";
import AuthLayout from "@/components/auth/AuthLayout";
import RegisterForm from "@/components/auth/RegisterForm";
import { AppRequest } from "@/services/api/requests";
import { useUser } from "@/stores/useUser";
import { successToast } from "@/components/toast";
import { useAuthNavigation, useLoader } from "@/context/authContext";

export default function Register() {
  const router = useRouter();
  const { getUser } = useUser();
  const { setAuthError } = useAuthNavigation();
  const { showLoader, hideLoader } = useLoader();

  const handleRegister = async (formData: { [key: string]: string }) => {
    console.log("=== REGISTER HANDLER CALLED ===");
    console.log("Form data received:", formData);
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
            has_permission: true
          },
          {
            name: "project:view",
            has_permission: true
          }
        ],
        role: "user", // Default role for new registrations
        company: formData.company,
        purpose: formData.purpose,
        user_type: "client"
      };

      console.log("Calling API endpoint: /auth/register");
      console.log("Payload:", payload);

      // Make the API call
      const response = await AppRequest.Post("/auth/register/", payload);
      console.log("Registration response-1:", response);
      if (response.data) {
        // Check if the response contains tokens
        if (response.data.token?.access_token) {
          // Store tokens
          localStorage.setItem("access_token", response.data.token.access_token);
          localStorage.setItem("refresh_token", response.data.token.refresh_token);

          setAuthError('');
          successToast("Registration successful!");

          // Redirect to dashboard
          router.push("/dashboard");
        } else {
          // If no tokens, registration successful but needs to login
          setAuthError('');
          successToast("Registration successful! Please login.");
          router.push("/login");
        }
      }

      hideLoader();
    } catch (error: any) {
      console.error("Registration error:", error);
      const errorMessage = error.response?.data?.detail ||
                          error.response?.data?.message ||
                          error.message ||
                          "Registration failed. Please try again.";
      setAuthError(errorMessage);
      hideLoader();
    }
  };

  return (
    <AuthLayout>
      <div className="flex flex-col justify-center items-center h-full">
        <RegisterForm onSubmit={handleRegister} />
      </div>
    </AuthLayout>
  );
}
