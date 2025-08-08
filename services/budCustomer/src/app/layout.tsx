import type { Metadata } from "next";
import localFont from 'next/font/local'
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { Theme } from "@radix-ui/themes";
import "@radix-ui/themes/styles.css";
import "./globals.css";
import { AuthNavigationProvider, LoaderProvider } from "@/context/authContext";
import { ThemeProvider } from "@/context/themeContext";

const geistSans = localFont({
  src: '../../public/fonts/Geist-VariableFont_wght.ttf',
  variable: "--font-geist-sans",
});

const geistMono = localFont({
  src: '../../public/fonts/GeistMono-VariableFont_wght.ttf',
  variable: "--font-geist-sans",
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
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-bud-bg-primary text-bud-text-primary`}
      >
        <ThemeProvider>
          <Theme appearance="inherit" accentColor="purple" grayColor="slate" radius="medium">
            <AuthNavigationProvider>
              <LoaderProvider>
                <AntdRegistry>{children}</AntdRegistry>
              </LoaderProvider>
            </AuthNavigationProvider>
          </Theme>
        </ThemeProvider>
      </body>
    </html>
  );
}
