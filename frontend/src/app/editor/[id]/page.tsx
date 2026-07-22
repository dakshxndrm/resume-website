import { EditorView } from "@/features/editor/components/EditorView";

export default function EditorPage({ params }: { params: { id: string } }) {
  return <EditorView id={params.id} />;
}
