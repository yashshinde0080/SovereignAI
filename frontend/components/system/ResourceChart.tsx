'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface ResourceChartProps {
  data: Array<{
    time: string;
    cpu: number;
    ram: number;
  }>;
}

export function ResourceChart({ data }: ResourceChartProps) {
  if (data.length === 0) {
    return (
      <div className="h-[300px] flex items-center justify-center text-muted-foreground">
        Waiting for data...
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="time"
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
        />
        <YAxis
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
          domain={[0, 100]}
          tickFormatter={(value) => `${value}%`}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '8px',
          }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="cpu"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
          dot={false}
          name="CPU"
        />
        <Line
          type="monotone"
          dataKey="ram"
          stroke="#22c55e"
          strokeWidth={2}
          dot={false}
          name="RAM"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}