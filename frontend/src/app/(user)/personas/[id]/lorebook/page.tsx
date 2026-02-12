export default function LorebookPage({ params }: { params: { id: string } }) {
  return (
    <div>
      <h1>Lorebook: Persona {params.id}</h1>
      {/* LorebookEditor 컴포넌트 */}
    </div>
  );
}
