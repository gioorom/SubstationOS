interface Props {
  title: string;
  value: string;
  icon: string;
}

export default function DashboardCard({
  title,
  value,
  icon,
}: Props) {
  return (
    <div className="border rounded-xl p-6 shadow-sm bg-white">
      <div className="text-3xl">
        {icon}
      </div>

      <h3 className="mt-4 text-lg font-semibold">
        {title}
      </h3>

      <p className="mt-2 text-2xl font-bold">
        {value}
      </p>
    </div>
  );
}