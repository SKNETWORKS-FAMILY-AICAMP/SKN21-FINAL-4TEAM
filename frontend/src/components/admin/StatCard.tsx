type Props = {
  title: string;
  value: string | number;
  description?: string;
};

export function StatCard({ title, value, description }: Props) {
  return (
    <div className="stat-card">
      <h3>{title}</h3>
      <p className="stat-value">{value}</p>
      {description && <p className="stat-desc">{description}</p>}
    </div>
  );
}
