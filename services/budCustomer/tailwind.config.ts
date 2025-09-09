import type { Config } from "tailwindcss";

const config = {
  important: true,
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      screens: {
        "1366px": "1366px", // Custom breakpoint for 1366px
        "1680px": "1680px", // Custom breakpoint for 1680px
        "1920px": "1920px", // Custom breakpoint for 1920px
        "2048px": "2048px", // Custom breakpoint for 2048px
        "2560px": "2560px", // Custom breakpoint for 2560px
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // BUD-specific color palette
        "bud-bg-primary": "var(--bg-primary)",
        "bud-bg-secondary": "var(--bg-secondary)",
        "bud-bg-tertiary": "var(--bg-tertiary)",
        "bud-text-primary": "var(--text-primary)",
        "bud-text-secondary": "var(--text-secondary)",
        "bud-text-muted": "var(--text-muted)",
        "bud-text-disabled": "var(--text-disabled)",
        "bud-border": "var(--border-color)",
        "bud-border-secondary": "var(--border-secondary)",
        "bud-border-transparent": "var(--border-transparent)",

        // Accent colors
        "bud-purple": "var(--color-purple)",
        "bud-purple-hover": "var(--color-purple-hover)",
        "bud-purple-active": "var(--color-purple-active)",
        "bud-yellow": "var(--color-yellow)",
        "bud-yellow-hover": "var(--color-yellow-hover)",
        "bud-yellow-active": "var(--color-yellow-active)",

        // Themed text colors
        "bud-primary-text": "var(--color-primary-text)",
        "bud-secondary-text": "var(--color-secondary-text)",
        "bud-accent-text": "var(--color-accent-text)",
        "bud-yellow-text": "var(--color-yellow-text)",

        // Status colors
        "bud-success": "var(--color-success)",
        "bud-warning": "var(--color-warning)",
        "bud-error": "var(--color-error)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        bounceIn: {
          "0%": { transform: "translateY(0) ", opacity: "0" },
          "50%": { transform: "translateY(-5%) scale(1.02)", opacity: "0.8" },
          "100%": { transform: "translateY(0) scale(1)", opacity: "1" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        bounceIn: "bounceIn 0.4s ease-out",
      },
      backgroundColor: {
        "custom-bg": "#000000",
      },
      backdropBlur: {
        custom: "10px",
      },
      boxShadow: {
        "purple-glow": "0px 0px 18px 0px #B882FA66",
      },
    },
  },
  plugins: [
    require("tailwindcss-animate"),
    require("@tailwindcss/line-clamp"),
    function ({ addUtilities }: { addUtilities: any }) {
      addUtilities({
        ".display-webkit-box": {
          display: "-webkit-box",
          "-webkit-box-orient": "vertical",
        },
      });
    },
  ],
} satisfies Config;

export default config;
