import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface SubjectCount {
  name: string;
  value: number;
}

export function SubjectDistributionChart({
  data,
  colors,
}: {
  data: SubjectCount[];
  colors: string[];
}) {
  return (
    <div role="img" aria-label="Document distribution by subject">
      <ResponsiveContainer width="56%" height={185}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            innerRadius={54}
            outerRadius={79}
            paddingAngle={4}
            stroke="none"
          >
            {data.map((item, index) => (
              <Cell
                key={item.name}
                fill={colors[index % colors.length]}
              />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
