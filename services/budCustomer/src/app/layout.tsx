import type { Metadata } from "next";
import localFont from "next/font/local";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { App } from "antd";
import "./globals.css";
import { AuthNavigationProvider, LoaderProvider } from "@/context/authContext";
import { ThemeProvider } from "@/context/themeContext";
import { ProjectProvider } from "@/context/projectContext";
import { NotificationProvider } from "@/components/NotificationProvider";
import { AppInitializer } from "@/components/AppInitializer";

const geistSans = localFont({
  src: "../../public/fonts/Geist-VariableFont_wght.ttf",
  variable: "--font-geist-sans",
});

const geistMono = localFont({
  src: "../../public/fonts/GeistMono-VariableFont_wght.ttf",
  variable: "--font-geist-sans",
});

export const metadata: Metadata = {
  title: "BUD Serve",
  description:
    "Useful. Private. Real time. Offline. Safe Intelligence in your Pocket.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-bud-bg-primary text-bud-text-primary`}
        suppressHydrationWarning={true}
      >
        <ThemeProvider>
          <AntdRegistry>
            <App>
              <NotificationProvider>
                <AppInitializer />
                <ProjectProvider>
                  <AuthNavigationProvider>
                    <LoaderProvider>{children}</LoaderProvider>
                  </AuthNavigationProvider>
                </ProjectProvider>
              </NotificationProvider>
            </App>
          </AntdRegistry>
        </ThemeProvider>
      </body>
    </html>
  );
}
