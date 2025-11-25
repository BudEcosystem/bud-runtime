import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./index.css";
import "./globals.scss";
import Toast from "./components/toast";
import { AuthProvider } from "./context/AuthContext";
import { ConfigProvider } from "./context/ConfigContext";
import { LoaderProvider, LoaderWrapper } from "./context/LoaderContext";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Bud Playground",
  description: "Bud Playground",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ConfigProvider>
          <AuthProvider>
            <LoaderProvider>
                {children}
              <Toast />
              <LoaderWrapper />
            </LoaderProvider>
          </AuthProvider>
        </ConfigProvider>
      </body>
    </html>
  );
}
