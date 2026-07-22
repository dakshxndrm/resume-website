import { ReportView } from "@/features/score/components/ReportView";

export default function ReportPage({ params }: { params: { id: string } }) {
  return <ReportView id={params.id} />;
}
