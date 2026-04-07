import { Dashboard } from "@/components/dashboard";
import { readDashboardStatus } from "@/lib/status";

export default function Page() {
  return <Dashboard initial={readDashboardStatus()} />;
}
