import AuthGuard from "@/components/auth/AuthGuard";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  // All non-auth pages should be protected by AuthGuard
  return <AuthGuard>{children}</AuthGuard>;
}
