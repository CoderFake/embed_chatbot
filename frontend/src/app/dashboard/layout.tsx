import { AdminLayout } from "@/components/admin/AdminLayout";
import { AuthGuard } from "@/components/AuthGuard";
import { ProgressToastProvider } from "@/contexts/progress-toast-context";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <ProgressToastProvider>
        <AdminLayout>{children}</AdminLayout>
      </ProgressToastProvider>
    </AuthGuard>
  );
}

