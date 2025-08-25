"use client";

import { useState, useEffect } from "react";
import { ThemeContext } from "./ThemeContext";
// import { ThemeProvider } from 'next-themes';
// import { Theme } from '@radix-ui/themes';

const ThemeContextProvider = ({ children }) => {
  const currentTheme =
    typeof window !== "undefined" ? localStorage.getItem("theme") : "";
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    if (theme == "dark") {
      root.className = "dark";
    } else if (theme == "light") {
      root.className = "light";
    } else {
      root.className = "light";
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prevTheme) => {
      const newTheme = prevTheme === "light" ? "dark" : "light";
      if (typeof window !== "undefined") {
        localStorage.setItem("theme", newTheme);
      }
      return newTheme;
    });
  };

  useEffect(() => {
    setTheme(currentTheme);
  }, [currentTheme]);

  return (
    <ThemeContext.Provider value={context}>{children}</ThemeContext.Provider>
  );
};

export default ThemeContextProvider;
