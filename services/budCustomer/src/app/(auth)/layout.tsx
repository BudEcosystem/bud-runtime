export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Auth pages should not have AuthGuard wrapper
  // They handle their own authentication logic
  return <>{children}</>;
}
