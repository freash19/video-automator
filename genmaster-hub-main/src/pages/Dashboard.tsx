import { useEffect, useState } from "react";
import { FileStack, CheckCircle, XCircle, Clock } from "lucide-react";
import { StatCard } from "@/components/dashboard/StatCard";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { API_BASE_URL } from "@/lib/utils";

export default function Dashboard() {
  const API = API_BASE_URL;
  const [totalEpisodes, setTotalEpisodes] = useState<number>(0);
  const [completed, setCompleted] = useState<number>(0);
  const [failed, setFailed] = useState<number>(0);
  const [avgTime, setAvgTime] = useState<string>("—");

  useEffect(() => {
    const load = async () => {
      try {
        const s = await fetch(`${API}/csv/stats`).then((r) => r.json());
        const p = await fetch(`${API}/progress`).then((r) => r.json());
        setTotalEpisodes((s?.episodes || []).length || 0);
        const done = Number(p?.done || 0);
        const total = Number(p?.total || 0);
        setCompleted(done);
        setFailed(total > 0 ? Math.max(0, total - done) : 0);
        const scenes = Number(s?.scenes || 0);
        const parts = Number(s?.parts || 1);
        const avgMin = parts ? Math.round((scenes ? scenes : 0) / parts) : 0;
        setAvgTime(avgMin ? `${avgMin}m` : "—");
      } catch (e) {
        // silent
      }
    };
    load();
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Панель</h1>
        <p className="text-muted-foreground">
          Обзор состояния автоматизации.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Всего эпизодов"
          value={totalEpisodes}
          icon={<FileStack className="w-6 h-6" />}
          variant="primary"
          delay={0}
        />
        <StatCard
          title="Завершено"
          value={completed}
          icon={<CheckCircle className="w-6 h-6" />}
          trend={{ value: 12, isPositive: true }}
          variant="success"
          delay={100}
        />
        <StatCard
          title="Ошибки"
          value={failed}
          icon={<XCircle className="w-6 h-6" />}
          trend={{ value: 5, isPositive: false }}
          variant="destructive"
          delay={200}
        />
        <StatCard
          title="Среднее время"
          value={avgTime}
          icon={<Clock className="w-6 h-6" />}
          trend={{ value: 8, isPositive: true }}
          variant="warning"
          delay={300}
        />
      </div>

      {/* Quick Actions & Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <QuickActions />
        <RecentActivity />
      </div>
    </div>
  );
}
