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
import AuthGuard from "@/components/auth/AuthGuard";
import { EnvironmentProvider } from "@/components/providers/EnvironmentProvider";
import { getServerEnvironment } from "@/lib/environment";

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
  // Get environment variables server-side (picks up both .env and runtime env)
  const environment = getServerEnvironment();

  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-bud-bg-primary text-bud-text-primary`}
        suppressHydrationWarning={true}
      >
        <EnvironmentProvider environment={environment}>
          <ThemeProvider>
            <AntdRegistry>
              <App>
                <NotificationProvider>
                  <AppInitializer />
                  <AuthNavigationProvider>
                    <LoaderProvider>
                      <ProjectProvider>{children}</ProjectProvider>
                    </LoaderProvider>
                  </AuthNavigationProvider>
                </NotificationProvider>
              </App>
            </AntdRegistry>
          </ThemeProvider>
        </EnvironmentProvider>
      </body>
    </html>
  );
}
