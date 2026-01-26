import { useEffect, useState } from "react";
import { CheckCircle, XCircle, Clock, Loader2 } from "lucide-react";
import { API_BASE_URL, cn } from "@/lib/utils";

interface Activity {
  id: string;
  status: "completed" | "failed" | "running" | "pending";
  episode: string;
  time: string;
  duration: string;
}

const statusConfig: Record<string, { icon: typeof CheckCircle; color: string; bg: string; animate?: string }> = {
  completed: { icon: CheckCircle, color: "text-success", bg: "bg-success/10" },
  failed: { icon: XCircle, color: "text-destructive", bg: "bg-destructive/10" },
  running: { icon: Loader2, color: "text-primary", bg: "bg-primary/10", animate: "animate-spin" },
  pending: { icon: Clock, color: "text-muted-foreground", bg: "bg-muted" },
};

export function RecentActivity() {
  const API = API_BASE_URL;
  const [activities, setActivities] = useState<Activity[]>([]);

  useEffect(() => {
    const tick = async () => {
      try {
        const recent: { recent?: string[] } = await fetch(`${API}/episodes/recent`).then((r) => r.json());
        const logs: Array<{ msg?: string }> = await fetch(`${API}/logs?limit=300`).then((r) => r.json());
        const recents: string[] = recent?.recent || [];
        const byEp: Record<string, Activity> = {};
        recents.forEach((ep) => {
          byEp[ep] = { id: ep, episode: ep, status: "pending", time: "—", duration: "—" };
        });
        logs.forEach((e) => {
          try {
            const raw = typeof e?.msg === "string" ? e.msg : "";
            const msg = raw ? JSON.parse(raw) : null;
            if (msg?.type === "start_part") {
              const ep = String(msg.episode);
              byEp[ep] = { id: ep, episode: ep, status: "running", time: "now", duration: "—" };
            }
            if (msg?.type === "finish_part") {
              const ep = String(msg.episode);
              const ok = Boolean(msg.ok);
              byEp[ep] = { id: ep, episode: ep, status: ok ? "completed" : "failed", time: "recent", duration: "—" };
            }
          } catch (err) {
            void err;
          }
        });
        const arr = Object.values(byEp);
        arr.sort((a, b) => a.episode.localeCompare(b.episode));
        setActivities(arr);
      } catch {
        setActivities([]);
      }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="rounded-xl border border-border p-6 shadow-card">
      <h3 className="text-lg font-semibold text-foreground mb-4">Недавняя активность</h3>
      <div className="space-y-3">
        {activities.map((activity) => {
          const config = statusConfig[activity.status as keyof typeof statusConfig];
          const Icon = config.icon;
          return (
            <div
              key={activity.id}
              className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
            >
              <div className={cn("p-2 rounded-lg", config.bg)}>
                <Icon className={cn("w-4 h-4", config.color, config.animate)} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">
                  {activity.episode}
                </p>
                <p className="text-xs text-muted-foreground">{activity.time}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-mono text-muted-foreground">{activity.duration}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
