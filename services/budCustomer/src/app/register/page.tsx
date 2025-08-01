"use client";
import React from "react";
import { useRouter } from "next/navigation";
import AuthLayout from "@/components/auth/AuthLayout";
import RegisterForm from "@/components/auth/RegisterForm";

export default function Register() {
  const router = useRouter();

  const handleRegister = async (data: any) => {
    try {
      // Mock registration logic - replace with your actual registration
      console.log("Registration attempt:", data);

      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Redirect to login after successful registration
      router.push("/login");
    } catch (error) {
      console.error("Registration error:", error);
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
