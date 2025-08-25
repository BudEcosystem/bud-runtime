import { createContext, useContext } from "react";

export const ThemeContext = createContext();

export const useThemeContext = () => useContext(ThemeContext);
