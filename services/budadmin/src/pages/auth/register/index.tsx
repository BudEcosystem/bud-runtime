/* eslint-disable react/no-unescaped-entities */
'use client';
import React, { createContext, useContext, useState } from 'react';
import Image from "next/image";
import * as Form from "@radix-ui/react-form";
import { Flex } from "@radix-ui/themes";
import { useRouter } from 'next/router';

// const inter = Inter({ subsets: ["latin"] });

export default function Register() {
  const router = useRouter();
  const [firstName, setFirstName] = useState('');
  const [lasttName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');

  var registerData;
  const prepareRegister = ()=> {
    if (password != confirmPassword) {

    }
    registerData = {
      'name': firstName + lasttName,
      'email': email,
      'password': password
    }
  }

  const handleLogin = async (e: { preventDefault: () => void; }) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(registerData),
      });
      if (response.ok) {
        const data = await response.json();
        // Store authentication token or session identifier in local storage
        localStorage.setItem('token', data.token);
        // Redirect to dashboard or home page
        router.push('/dashboard');
      } else {
        setError('Invalid username or password');
      }
    } catch (error) {
      console.error('Login error:', error);
      setError('Something went wrong');
    }
  };
  return (
    <div className="w-full h-screen logginBg">
      <div className="loginWrap w-full flex justify-between">
        <div className="loginLeft w-[43.35%] py-[8.6%] px-[7.3%] pr-[4.4%]">
          <h1 className="text-white text-[2em] font-medium tracking-[.03em]">Welcome to our page</h1>
          <h2 className="text-[#696969] text-[1.03em] font-medium tracking-[.02em] py-[.5em]">Please enter your details</h2>
          <Form.Root className="w-[100%] mt-[2.8em]">
            <Flex gap="3" justify="between">
              <Form.Field className="grid mb-[10px] w=[48%]" name="email">
                <div className="flex items-baseline justify-between">
                  <Form.Message
                    className="text-[13px] text-white opacity-[0.8]"
                    match="valueMissing"
                  >
                    Please enter your First Name
                  </Form.Message>
                  <Form.Message
                    className="text-[13px] text-white opacity-[0.8]"
                    match="typeMismatch"
                  >
                    Please provide a valid First Name
                  </Form.Message>
                </div>
                <Form.Control asChild>
                  <input
                    placeholder="First Name"
                    className="specialInput text-[#696969] box-border w-full bg-[transparent] shadow-blackA6 inline-flex h-[35px] appearance-none items-center justify-center rounded-[4px]  text-[1.1em] leading-none shadow-[0_0_0_1px] outline-none hover:shadow-[0_0_0_1px_black] focus:shadow-[0_0_0_2px_black] selection:color-white selection:bg-black"
                    type="text"
                    required
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                  />
                </Form.Control>
              </Form.Field>
              <Form.Field className="grid mb-[10px] w-[48%]" name="email">
                <div className="flex items-baseline justify-between">
                  <Form.Message
                    className="text-[13px] text-white opacity-[0.8]"
                    match="valueMissing"
                  >
                    Please enter your Last Name
                  </Form.Message>
                  <Form.Message
                    className="text-[13px] text-white opacity-[0.8]"
                    match="typeMismatch"
                  >
                    Please provide a valid Last Name
                  </Form.Message>
                </div>
                <Form.Control asChild>
                  <input
                    placeholder="Last Name"
                    className="text-[#696969] specialInput box-border w-full bg-blackA2 shadow-blackA6 inline-flex h-[35px] appearance-none items-center justify-center rounded-[4px]  text-[1.1em] leading-none  shadow-[0_0_0_1px] outline-none hover:shadow-[0_0_0_1px_black] focus:shadow-[0_0_0_2px_black] selection:color-white selection:bg-blackA6"
                    type="text"
                    required
                    value={lasttName}
                    onChange={(e) => setLastName(e.target.value)}
                  />
                </Form.Control>
              </Form.Field>
            </Flex>
            <Form.Field className="grid mb-[10px]" name="email">
              <div className="flex items-baseline justify-between">
                <Form.Message
                  className="text-[13px] text-white opacity-[0.8]"
                  match="valueMissing"
                >
                  Please enter your email
                </Form.Message>
                <Form.Message
                  className="text-[13px] text-white opacity-[0.8]"
                  match="typeMismatch"
                >
                  Please provide a valid email
                </Form.Message>
              </div>
              <Form.Control asChild>
                <input
                placeholder="Email"
                  className="box-border w-full specialInput bg-blackA2 shadow-blackA6 inline-flex h-[35px] appearance-none items-center justify-center rounded-[4px]  text-[1.1em] leading-none text-white shadow-[0_0_0_1px] outline-none hover:shadow-[0_0_0_1px_black] focus:shadow-[0_0_0_2px_black] selection:color-white selection:bg-blackA6"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Form.Control>
            </Form.Field>
            <Form.Field className="grid mb-[10px]" name="question">
              <div className="flex items-baseline justify-between">
                <Form.Message
                  className="text-[13px] text-white opacity-[0.8]"
                  match="valueMissing"
                >
                  Please enter your password
                </Form.Message>
              </div>
              <Form.Control asChild>
                <input
                  placeholder="Password"
                  className="box-border w-full specialInput bg-blackA2 shadow-blackA6 inline-flex h-[35px] appearance-none items-center justify-center rounded-[4px]  text-[1.1em] leading-none text-white shadow-[0_0_0_1px] outline-none hover:shadow-[0_0_0_1px_black] focus:shadow-[0_0_0_2px_black] selection:color-white selection:bg-blackA6"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Form.Control>
            </Form.Field>
            <Form.Field className="grid mb-[10px]" name="question">
              <div className="flex items-baseline justify-between">
                <Form.Message
                  className="text-[13px] text-white opacity-[0.8]"
                  match="valueMissing"
                >
                  Please re-enter your password
                </Form.Message>
              </div>
              <Form.Control asChild>
                <input
                  placeholder="Confirm Password"
                  className="box-border w-full specialInput bg-blackA2 shadow-blackA6 inline-flex h-[35px] appearance-none items-center justify-center rounded-[4px]  text-[1.1em] leading-none text-white shadow-[0_0_0_1px] outline-none hover:shadow-[0_0_0_1px_black] focus:shadow-[0_0_0_2px_black] selection:color-white selection:bg-blackA6"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </Form.Control>
            </Form.Field>
            <div className="text-white text-[1.08em] whoAmIWrapLabelOne font-semibold	mb-[.4em] mt-[2.9em]">Number of employees</div>
            <div className="whoAmIWrap mt-[1.2em] mb-[2.9em]">
              <div className="whoAmI h-[5.2em] mb-[1em] flex justify-start align-middle border border-[#414141] rounded-lg p-[.6em]">
                <div className="IcnWrap border border-[#414141] rounded-lg	w-[3.35em] h-[3.35em] p-[0.8em] m-[.25em]">
                  <Image

                  src="/icons/single.png"
                  width={20}
                  height={20}
                  alt=""
                  style={{width: "100%", height: "100%"}}
                  />
                </div>
                <div className="whoAmIWrapLabelWrap text-white pl-[.07em]">
                  <div className="whoAmIWrapLabelOne text-[1.08em] whoAmIWrapLabelOne font-semibold	mb-[.4em]">I'm a solo creator</div>
                  <div className="whoAmIWrapLabelTwo text-[#bbbbbb] text-[1.08em] whoAmIWrapLabelOne font-semibold	">I need to setup an account for myself.</div>
                </div>
              </div>
              <div className="whoAmI h-[5.2em] flex justify-start align-middle border border-[#414141] rounded-lg p-[.6em]">
                <div className="IcnWrap border border-[#414141] rounded-lg		w-[3.35em] h-[3.35em] p-[0.8em] m-[.25em]">
                  <Image

                  src="/icons/double.png"
                  width={20}
                  height={20}
                  alt=""
                  style={{width: "100%", height: "100%"}}
                  />
                </div>
                <div className="whoAmIWrapLabelWrap text-white pl-[.07em]">
                  <div className="whoAmIWrapLabelOne text-[1.08em] whoAmIWrapLabelOne font-semibold	mb-[.4em]">I'm part of a team</div>
                  <div className="whoAmIWrapLabelTwo text-[#bbbbbb] text-[1.08em] whoAmIWrapLabelOne font-semibold	">I need to setup an account for team.</div>
                </div>
              </div>
            </div>
            <Form.Submit asChild>
              <button className="p-[1.35em] text-[1.15em] box-border w-full font-bold text-black shadow-blackA4 hover:bg-mauve3 inline-flex h-[35px] items-center justify-center rounded-lg bg-white px-[1.1em] leading-none shadow-[0_2px_10px] focus:shadow-[0_0_0_2px] focus:shadow-black focus:outline-none mt-[10px] ">
                Register
              </button>
            </Form.Submit>
          </Form.Root>
        </div>
        <div className="loginRight w-[57%] h-screen">
          <div className="loginBg rounded-2xl"></div>
        </div>
      </div>
    </div>
  );
}
