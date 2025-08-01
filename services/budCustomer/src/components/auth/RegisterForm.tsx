"use client";
import React, { useEffect, useState } from "react";
import {
  Text_12_300_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_32_500_FFFFFF,
  Text_18_400_EEEEEE,
} from "@/components/ui/text";
import { useAuthNavigation } from "@/context/authContext";
import { PrimaryButton } from "@/components/ui/button";
import { motion } from "framer-motion";
import { getChromeColor } from "@/utils/getChromeColor";

type RegisterFormProps = {
  onSubmit: (formData: { [key: string]: string }) => void;
};

const RegisterForm = ({ onSubmit }: RegisterFormProps) => {
  const { setActivePage, authError, setAuthError } = useAuthNavigation();
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
    company: "",
    purpose: "",
    role: "",
  });
  const [errors, setErrors] = useState<{[key: string]: string}>({});
  const [submittable, setSubmittable] = useState(false);
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    // Check if form is submittable
    const requiredFields = ['name', 'email', 'password', 'confirmPassword', 'company', 'purpose', 'role'];
    const isFormValid = requiredFields.every(field => {
      const value = formData[field as keyof typeof formData];
      if (field === 'email') return value.length >= 3 && emailRegex.test(value);
      if (field === 'password' || field === 'confirmPassword') return value.length >= 8;
      return value.length > 0;
    }) && formData.password === formData.confirmPassword;

    setSubmittable(isFormValid);
  }, [formData, emailRegex]);

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));

    // Clear errors when user starts typing
    if (value) {
      setErrors(prev => ({ ...prev, [field]: '' }));
      setAuthError('');
    }
  };

  const validateField = (field: string, value: string) => {
    let error = '';

    switch (field) {
      case 'email':
        if (!value) error = 'Please input your email!';
        else if (value.length >= 3 && !emailRegex.test(value)) error = 'Please enter a valid email';
        break;
      case 'password':
        if (!value) error = 'Please input your password!';
        else if (value.length < 8) error = 'Password must be at least 8 characters long';
        break;
      case 'confirmPassword':
        if (!value) error = 'Please confirm your password!';
        else if (value !== formData.password) error = 'Passwords do not match';
        break;
      case 'name':
        if (!value) error = 'Please input your name!';
        break;
      case 'company':
        if (!value) error = 'Please input your company!';
        break;
      case 'purpose':
        if (!value) error = 'Please specify your purpose!';
        break;
      case 'role':
        if (!value) error = 'Please input your role!';
        break;
    }

    setErrors(prev => ({ ...prev, [field]: error }));
    return !error;
  };

  const handleRegister = (e: { preventDefault: () => void }) => {
    e.preventDefault();
    if (!submittable) return;

    const { confirmPassword, ...submitData } = formData;
    onSubmit(submitData);
  };

  if (!mounted) {
    return null;
  }

  return (
    <>
      <div className="mb-8">
        <div className="flex justify-center items-center mb-[.9rem]">
          <Text_32_500_FFFFFF className="tracking-[.01em] leading-[100%] text-center">
            Create Account
          </Text_32_500_FFFFFF>
        </div>
        <Text_12_400_B3B3B3 className="text-center">
          Enter your details to create your BUD account
        </Text_12_400_B3B3B3>
      </div>

      <form
        onSubmit={handleRegister}
        className="w-[76.6%] mt-[1.6em]"
      >
        {/* Name Field */}
        <div className="mb-[1.8rem]">
          <div className="relative">
            <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block tracking-[.035rem] z-10">
              Name
            </Text_12_300_EEEEEE>
          </div>
          <input
            type="text"
            placeholder="Enter your full name"
            value={formData.name}
            onChange={(e) => handleInputChange('name', e.target.value)}
            onBlur={() => validateField('name', formData.name)}
            className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none border rounded-[6px] pt-[.8rem] pb-[.53rem] px-3 bg-transparent
              ${errors.name ? 'border-red-500' : 'border-gray-600 focus:border-gray-400'}`}
          />
          {errors.name && (
            <div className="text-red-500 text-xs mt-1">{errors.name}</div>
          )}
        </div>

        {/* Email Field */}
        <div className="mb-[1.8rem]">
          <div className="relative">
            <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block tracking-[.035rem] z-10">
              Email
            </Text_12_300_EEEEEE>
          </div>
          <input
            type="email"
            placeholder="Enter email"
            value={formData.email}
            onChange={(e) => handleInputChange('email', e.target.value)}
            onBlur={() => validateField('email', formData.email)}
            className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none border rounded-[6px] pt-[.8rem] pb-[.53rem] px-3 bg-transparent
              ${errors.email ? 'border-red-500' : 'border-gray-600 focus:border-gray-400'}`}
          />
          {errors.email && (
            <div className="text-red-500 text-xs mt-1">{errors.email}</div>
          )}
        </div>

        {/* Password Fields */}
        <div className="flex gap-4 mb-[1.8rem]">
          <div className="flex-1">
            <div className="relative">
              <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block tracking-[.035rem] z-10">
                Password
              </Text_12_300_EEEEEE>
            </div>
            <input
              type="password"
              placeholder="Enter password"
              value={formData.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              onBlur={() => validateField('password', formData.password)}
              className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none border rounded-[6px] pt-[.8rem] pb-[.53rem] px-3 bg-transparent
                ${errors.password ? 'border-red-500' : 'border-gray-600 focus:border-gray-400'}`}
            />
            {errors.password && (
              <div className="text-red-500 text-xs mt-1">{errors.password}</div>
            )}
          </div>

          <div className="flex-1">
            <div className="relative">
              <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block tracking-[.035rem] z-10">
                Confirm Password
              </Text_12_300_EEEEEE>
            </div>
            <input
              type="password"
              placeholder="Confirm password"
              value={formData.confirmPassword}
              onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
              onBlur={() => validateField('confirmPassword', formData.confirmPassword)}
              className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none border rounded-[6px] pt-[.8rem] pb-[.53rem] px-3 bg-transparent
                ${errors.confirmPassword ? 'border-red-500' : 'border-gray-600 focus:border-gray-400'}`}
            />
            {errors.confirmPassword && (
              <div className="text-red-500 text-xs mt-1">{errors.confirmPassword}</div>
            )}
          </div>
        </div>

        {/* Company Field */}
        <div className="mb-[1.8rem]">
          <div className="relative">
            <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block tracking-[.035rem] z-10">
              Company
            </Text_12_300_EEEEEE>
          </div>
          <input
            type="text"
            placeholder="Enter company name"
            value={formData.company}
            onChange={(e) => handleInputChange('company', e.target.value)}
            onBlur={() => validateField('company', formData.company)}
            className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none border rounded-[6px] pt-[.8rem] pb-[.53rem] px-3 bg-transparent
              ${errors.company ? 'border-red-500' : 'border-gray-600 focus:border-gray-400'}`}
          />
          {errors.company && (
            <div className="text-red-500 text-xs mt-1">{errors.company}</div>
          )}
        </div>

        {/* Purpose Field */}
        <div className="mb-[1.8rem]">
          <div className="relative">
            <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block tracking-[.035rem] z-10">
              Purpose
            </Text_12_300_EEEEEE>
          </div>
          <input
            type="text"
            placeholder="What will you use BUD for?"
            value={formData.purpose}
            onChange={(e) => handleInputChange('purpose', e.target.value)}
            onBlur={() => validateField('purpose', formData.purpose)}
            className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none border rounded-[6px] pt-[.8rem] pb-[.53rem] px-3 bg-transparent
              ${errors.purpose ? 'border-red-500' : 'border-gray-600 focus:border-gray-400'}`}
          />
          {errors.purpose && (
            <div className="text-red-500 text-xs mt-1">{errors.purpose}</div>
          )}
        </div>

        {/* Role Field */}
        <div className="mb-[1.8rem]">
          <div className="relative">
            <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block tracking-[.035rem] z-10">
              Role
            </Text_12_300_EEEEEE>
          </div>
          <input
            type="text"
            placeholder="Enter your role"
            value={formData.role}
            onChange={(e) => handleInputChange('role', e.target.value)}
            onBlur={() => validateField('role', formData.role)}
            className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none border rounded-[6px] pt-[.8rem] pb-[.53rem] px-3 bg-transparent
              ${errors.role ? 'border-red-500' : 'border-gray-600 focus:border-gray-400'}`}
          />
          {errors.role && (
            <div className="text-red-500 text-xs mt-1">{errors.role}</div>
          )}
        </div>

        <PrimaryButton
          type="submit"
          classNames="w-[100%] mt-[1.6rem]"
          disabled={!submittable}
        >
          Create Account
        </PrimaryButton>
      </form>

      <div className="mt-[2.2rem] flex justify-center">
        <Text_12_400_EEEEEE className="cursor-pointer">
          Already have an account?{" "}
          <span
            className="text-[#965CDE] cursor-pointer"
            onClick={() => setActivePage(1)}
          >
            Sign in
          </span>
        </Text_12_400_EEEEEE>
      </div>

      {authError && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeIn" }}
          className="border-[1px] border-[#EC7575] rounded-[6px] px-[.5rem] py-[1rem] flex justify-center items-center w-[76.6%] mt-[1.5rem]"
          style={{
            backgroundColor: getChromeColor("#EC7575"),
          }}
        >
          <Text_12_400_EEEEEE className="text-[#EC7575]">
            {authError.includes('Cannot read properties') ? 'Something went wrong, please try again later.' : authError}
          </Text_12_400_EEEEEE>
        </motion.div>
      )}
    </>
  );
};

export default RegisterForm;
