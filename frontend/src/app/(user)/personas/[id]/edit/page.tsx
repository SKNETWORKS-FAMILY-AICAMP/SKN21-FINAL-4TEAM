export default function EditPersonaPage({ params }: { params: { id: string } }) {
  return (
    <div>
      <h1>Edit Persona: {params.id}</h1>
      {/* PersonaForm 컴포넌트 (편집 모드) */}
    </div>
  );
}
