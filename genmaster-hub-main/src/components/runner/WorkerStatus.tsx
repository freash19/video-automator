import { useEffect, useState } from "react";
import { Loader2, CheckCircle, Clock, XCircle } from "lucide-react";
import { API_BASE_URL, cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

interface Worker {
  id: number;
  status: "running" | "idle" | "completed" | "error";
  currentEpisode?: string;
  progress?: number;
}

const initialWorkers: Worker[] = [
  { id: 1, status: "idle" },
  { id: 2, status: "idle" },
  { id: 3, status: "idle" },
  { id: 4, status: "idle" },
];

const statusConfig: Record<string, { icon: typeof Loader2; color: string; bg: string; label: string; animate?: string }> = {
  running: {
    icon: Loader2,
    color: "text-primary",
    bg: "bg-primary/10",
    label: "В работе",
    animate: "animate-spin",
  },
  idle: {
    icon: Clock,
    color: "text-muted-foreground",
    bg: "bg-muted",
    label: "Ожидание",
  },
  completed: {
    icon: CheckCircle,
    color: "text-success",
    bg: "bg-success/10",
    label: "Готово",
  },
  error: {
    icon: XCircle,
    color: "text-destructive",
    bg: "bg-destructive/10",
    label: "Ошибка",
  },
};

export function WorkerStatus() {
  const API = API_BASE_URL;
  const [workers, setWorkers] = useState<Worker[]>(initialWorkers);

  useEffect(() => {
    const tick = async () => {
      try {
        const p: { done?: number; total?: number } = await fetch(`${API}/progress`).then((r) => r.json());
        const logs: Array<{ msg?: string }> = await fetch(`${API}/logs?limit=200`).then((r) => r.json());
        const running: Record<string, number> = {};
        logs.forEach((e) => {
          try {
            const raw = typeof e?.msg === "string" ? e.msg : "";
            const msg = raw ? JSON.parse(raw) : null;
            if (msg?.type === "start_part") {
              running[String(msg.episode)] = Number(msg.part);
            }
            if (msg?.type === "finish_part") {
              delete running[String(msg.episode)];
            }
          } catch (err) {
            void err;
          }
        });
        const episodes = Object.keys(running);
        const done = Number(p?.done || 0);
        const total = Number(p?.total || 0);
        const progress = total ? Math.round((done / total) * 100) : 0;
        const next: Worker[] = initialWorkers.map((w, idx) => {
          const ep = episodes[idx];
          if (ep) {
            return { id: w.id, status: "running", currentEpisode: ep, progress };
          }
          return { id: w.id, status: "idle" };
        });
        setWorkers(next);
      } catch {
        setWorkers(initialWorkers);
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="rounded-xl border border-border shadow-card p-4">
      <h3 className="text-sm font-semibold text-foreground mb-4">Статус воркеров</h3>
      <div className="grid grid-cols-1 gap-3">
        {workers.map((worker) => {
          const config = statusConfig[worker.status];
          const Icon = config.icon;

          return (
            <div
              key={worker.id}
              className={cn(
                "p-3 rounded-lg border transition-all duration-200",
                worker.status === "running" ? "border-primary/30 bg-primary/5" : "border-border"
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-muted-foreground">
                  Воркер {worker.id}
                </span>
                <div className={cn("flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px]", config.bg)}>
                  <Icon className={cn("w-3 h-3", config.color, config.animate)} />
                  <span className={config.color}>{config.label}</span>
                </div>
              </div>

              {worker.currentEpisode && (
                <div className="space-y-1.5">
                  <div className="text-sm font-mono text-foreground">{worker.currentEpisode}</div>
                  {worker.progress !== undefined && (
                    <Progress value={worker.progress} className="h-1" />
                  )}
                </div>
              )}

              {!worker.currentEpisode && (
                <div className="text-sm text-muted-foreground/50 italic">Ожидание...</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
