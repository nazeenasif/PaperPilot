import { SummaryView } from "@/components/summary/SummaryView";

export default async function SummaryPage({ params }: { params: Promise<{ paperId: string }> }) {
  const { paperId } = await params;
  return <SummaryView paperId={paperId} />;
}
