export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex' }}>
      <nav>{/* Sidebar 컴포넌트 */}</nav>
      <main style={{ flex: 1 }}>{children}</main>
    </div>
  );
}
