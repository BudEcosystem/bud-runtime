import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { Theme } from "@radix-ui/themes";
import "@radix-ui/themes/styles.css";
import "./globals.css";
import { AuthNavigationProvider, LoaderProvider } from "@/context/authContext";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "BUD Serve",
  description: "Useful. Private. Real time. Offline. Safe Intelligence in your Pocket.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased dark:bg-[#101010] dark:text-[#EEEEEE]`}
      >
        <Theme appearance="dark" accentColor="purple" grayColor="slate" radius="medium">
          <AuthNavigationProvider>
            <LoaderProvider>
              <AntdRegistry>{children}</AntdRegistry>
            </LoaderProvider>
          </AuthNavigationProvider>
        </Theme>
      </body>
    </html>
  );
}
