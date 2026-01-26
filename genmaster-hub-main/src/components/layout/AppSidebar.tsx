import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Database,
  GitBranch,
  Settings,
  Play,
  ChevronLeft,
  ChevronRight,
  Zap,
  FolderOutput,
  FileStack,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { API_BASE_URL } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  { path: "/data-studio", icon: Database, label: "Студия данных", description: "Шаг 1: Импорт данных" },
  { path: "/workflow", icon: GitBranch, label: "Воркфлоу", description: "Шаг 2: Конструктор" },
  { path: "/settings", icon: Settings, label: "Настройки", description: "Конфигурация" },
  { path: "/runner", icon: Play, label: "Запуск", description: "Выполнение автоматизации" },
  { path: "/results", icon: FolderOutput, label: "Видео", description: "Выходные видео" },
];

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const API = API_BASE_URL;
  const [stats, setStats] = useState({
    totalEpisodes: 0,
    completed: 0,
    failed: 0,
    mergedTotal: "—",
  });
  const [tasks, setTasks] = useState<Array<{ label: string; detail?: string }>>([]);

  const parseDuration = (val: string) => {
    const v = String(val || "").trim();
    if (!v) return 0;
    if (v.endsWith("s")) {
      const n = Number(v.replace("s", ""));
      return Number.isFinite(n) ? n : 0;
    }
    const parts = v.split(":").map((p) => Number(p));
    if (parts.some((p) => Number.isNaN(p))) return 0;
    if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    }
    if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    }
    return 0;
  };

  const formatDuration = (seconds: number) => {
    if (!Number.isFinite(seconds) || seconds <= 0) return "—";
    const s = Math.floor(seconds);
    if (s < 60) return `${s}s`;
    if (s < 3600) {
      const m = Math.floor(s / 60);
      const sec = s % 60;
      return `${m}:${String(sec).padStart(2, "0")}`;
    }
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };

  useEffect(() => {
    if (collapsed) return;
    const load = async () => {
      try {
        const [s, p, logs, vids] = await Promise.all([
          fetch(`${API}/csv/stats`).then((r) => r.json()),
          fetch(`${API}/progress`).then((r) => r.json()),
          fetch(`${API}/logs?limit=200`).then((r) => r.json()),
          fetch(`${API}/videos`).then((r) => r.json()),
        ]);
        const totalEpisodes = (s?.episodes || []).length || 0;
        const done = Number(p?.done || 0);
        const total = Number(p?.total || 0);
        const failed = total > 0 ? Math.max(0, total - done) : 0;
        const mergedVideos = Array.isArray(vids?.videos) ? vids.videos : [];
        const mergedSeconds = mergedVideos.reduce((acc: number, v: Record<string, unknown>) => {
          if (!v?.merged) return acc;
          const sec = typeof v.duration_sec === "number" ? v.duration_sec : parseDuration(String(v.duration || ""));
          return acc + (Number.isFinite(sec) ? sec : 0);
        }, 0);
        setStats({
          totalEpisodes,
          completed: done,
          failed,
          mergedTotal: formatDuration(mergedSeconds),
        });

        const running: Record<string, number> = {};
        let mergeActive = false;
        if (Array.isArray(logs)) {
          logs.forEach((e) => {
            const raw = typeof e?.msg === "string" ? e.msg : "";
            try {
              const msg = raw ? JSON.parse(raw) : null;
              if (msg?.type === "start_part") {
                running[String(msg.episode)] = Number(msg.part);
              }
              if (msg?.type === "finish_part") {
                delete running[String(msg.episode)];
              }
            } catch {
              if (raw.includes("merge_videos") && raw.includes("merging")) {
                mergeActive = true;
              }
              if (raw.includes("merge complete")) {
                mergeActive = false;
              }
            }
          });
        }

        const taskList: Array<{ label: string; detail?: string }> = [];
        if (total > 0 && done < total) {
          taskList.push({ label: "Заполнение сценария", detail: `${done}/${total}` });
        }
        Object.entries(running).forEach(([episode, part]) => {
          taskList.push({ label: "Эпизод в работе", detail: `${episode}, часть ${part}` });
        });
        if (mergeActive) {
          taskList.push({ label: "Монтаж видео", detail: "склейка/рендер" });
        }
        setTasks(taskList);
      } catch {
        setTasks([]);
      }
    };
    load();
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [API, collapsed]);

  return (
    <aside
      className={cn(
        "relative flex flex-col h-screen border-r border-sidebar-border bg-sidebar transition-all duration-300",
        collapsed ? "w-[72px]" : "w-[260px]"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 p-4 border-b border-sidebar-border">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl gradient-primary shadow-glow">
          <Zap className="w-5 h-5 text-primary-foreground" />
        </div>
        {!collapsed && (
          <div className="flex flex-col animate-fade-in">
            <span className="text-sm font-semibold text-foreground">HeyGen</span>
            <span className="text-xs text-muted-foreground">Автоматизация Pro</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto scrollbar-thin">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          const Icon = item.icon;

          const linkContent = (
            <NavLink
              to={item.path}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 group",
                isActive
                  ? "bg-sidebar-accent text-sidebar-primary"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )}
            >
              <div
                className={cn(
                  "flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-200",
                  isActive
                    ? "bg-primary/20 text-primary"
                    : "bg-muted/50 text-muted-foreground group-hover:bg-accent group-hover:text-accent-foreground"
                )}
              >
                <Icon className="w-4 h-4" />
              </div>
              {!collapsed && (
                <div className="flex flex-col animate-fade-in">
                  <span className="text-sm font-medium">{item.label}</span>
                  <span className="text-[10px] text-muted-foreground">{item.description}</span>
                </div>
              )}
              {isActive && !collapsed && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              )}
            </NavLink>
          );

          if (collapsed) {
            return (
              <Tooltip key={item.path} delayDuration={0}>
                <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                <TooltipContent side="right" className="flex flex-col gap-0.5">
                  <span className="font-medium">{item.label}</span>
                  <span className="text-xs text-muted-foreground">{item.description}</span>
                </TooltipContent>
              </Tooltip>
            );
          }

          return <div key={item.path}>{linkContent}</div>;
        })}
      </nav>

      {!collapsed && (
        <div className="px-3 pb-3 space-y-3 border-t border-sidebar-border pt-3">
          <div className="rounded-lg border border-border bg-muted/20 p-3">
            <div className="text-xs font-semibold text-foreground mb-2 flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-primary" />
              Статистика
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-md border border-border p-2">
                <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <FileStack className="w-3 h-3" />
                  Всего
                </div>
                <div className="text-lg font-semibold">{stats.totalEpisodes}</div>
              </div>
              <div className="rounded-md border border-border p-2">
                <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" />
                  Завершено
                </div>
                <div className="text-lg font-semibold">{stats.completed}</div>
              </div>
              <div className="rounded-md border border-border p-2">
                <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <XCircle className="w-3 h-3" />
                  Ошибки
                </div>
                <div className="text-lg font-semibold">{stats.failed}</div>
              </div>
              <div className="rounded-md border border-border p-2">
                <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  Сумма монтажа
                </div>
                <div className="text-lg font-semibold">{stats.mergedTotal}</div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-muted/20 p-3">
            <div className="text-xs font-semibold text-foreground mb-2">Текущие задачи</div>
            {tasks.length === 0 ? (
              <div className="text-xs text-muted-foreground/70 italic">Нет активных задач</div>
            ) : (
              <div className="space-y-2">
                {tasks.map((t, idx) => (
                  <div key={`${t.label}-${idx}`} className="rounded-md border border-border p-2">
                    <div className="text-xs font-medium text-foreground">{t.label}</div>
                    {t.detail && (
                      <div className="text-[10px] text-muted-foreground">{t.detail}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Collapse Toggle */}
      <div className="p-3 border-t border-sidebar-border">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCollapsed(!collapsed)}
          className="w-full justify-center"
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span className="animate-fade-in">Свернуть</span>
            </>
          )}
        </Button>
      </div>
    </aside>
  );
}
