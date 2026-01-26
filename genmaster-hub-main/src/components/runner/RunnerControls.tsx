import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Play, Square, Pause, RefreshCw, AlertTriangle, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { API_BASE_URL, cn, formatDateTimeRu, projectStatusRu } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ProjectEditorDialog } from "@/components/projects/ProjectEditorDialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { useSearchParams } from "react-router-dom";
import { Checkbox } from "@/components/ui/checkbox";

type RunnerState = "idle" | "running" | "paused" | "completed";

interface SavedProject {
  episode: string;
  status: string;
  created_at?: string;
  stats?: {
    parts?: number;
    scenes?: number;
    rows?: number;
    speakers?: string[];
    brolls?: number;
    template_url?: string | null;
  };
}

type TaskStatus = "queued" | "running" | "paused" | "success" | "failed" | "stopped";
interface RunnerTask {
  key: string;
  episode: string;
  part: number;
  status: TaskStatus;
  stage?: string;
  error?: string;
  started_at?: number | null;
  finished_at?: number | null;
  scene_done?: number;
  scene_total?: number;
  report?: Record<string, unknown> | null;
}

export function RunnerControls() {
  const API = API_BASE_URL;
  const [state, setState] = useState<RunnerState>("idle");
  const [progress, setProgress] = useState(0);
  const [doneParts, setDoneParts] = useState(0);
  const [totalParts, setTotalParts] = useState(0);
  const [doneScenes, setDoneScenes] = useState(0);
  const [totalScenes, setTotalScenes] = useState(0);
  const [workflows, setWorkflows] = useState<string[]>([]);
  const [selectedWf, setSelectedWf] = useState<string>("");
  const [projects, setProjects] = useState<SavedProject[]>([]);
  const [selectedEpisodes, setSelectedEpisodes] = useState<Record<string, boolean>>({});
  const [projectFilter, setProjectFilter] = useState<string>("all");
  const [editingEpisode, setEditingEpisode] = useState<string | null>(null);
  const [initialSelectionApplied, setInitialSelectionApplied] = useState(false);
  const [autostartTriggered, setAutostartTriggered] = useState(false);
  const [searchParams] = useSearchParams();
  const [tasks, setTasks] = useState<RunnerTask[]>([]);
  const lastTaskStatusRef = useRef<Record<string, TaskStatus>>({});

  const queryEpisodes = useMemo(() => {
    const raw = (searchParams.get("episodes") || "").trim();
    if (!raw) return [];
    return raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }, [searchParams]);

  const queryAutostart = useMemo(() => {
    const v = (searchParams.get("autostart") || "").trim();
    return v === "1" || v.toLowerCase() === "true";
  }, [searchParams]);

  const sendBrowserNotification = useCallback((title: string, body: string) => {
    try {
      if (typeof window === "undefined") return;
      if (!("Notification" in window)) return;
      const show = () => {
        try {
          new Notification(title, { body });
        } catch (e) {
          void e;
        }
      };
      if (Notification.permission === "granted") {
        show();
        return;
      }
      return;
    } catch (e) {
      void e;
    }
  }, []);

  const startEpisodes = useCallback(
    async (episodes: string[]) => {
      const eps = episodes.filter(Boolean);
      if (eps.length === 0) {
        toast.error("Не выбраны проекты для запуска");
        return;
      }
      try {
        const res = await fetch(`${API}/run/projects`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workflow: selectedWf || null, episodes: eps }),
        });
        if (!res.ok) {
          const t = await res.text().catch(() => "");
          throw new Error(t || `HTTP ${res.status}`);
        }
        setState("running");
      } catch (e) {
        toast.error("Не удалось запустить проекты");
      }
    },
    [API, selectedWf]
  );

  const handleStart = useCallback(() => {
    if (state === "paused") {
      fetch(`${API}/resume`, { method: "POST" }).then(() => setState("running"));
      return;
    }
    const eps = Object.keys(selectedEpisodes).filter((k) => selectedEpisodes[k]);
    void startEpisodes(eps);
  }, [API, selectedEpisodes, startEpisodes, state]);

  const handleEditorOpenChange = useCallback((open: boolean) => {
    if (!open) setEditingEpisode(null);
  }, []);

  const toggleEpisode = useCallback((episode: string) => {
    setSelectedEpisodes((prev) => ({ ...prev, [episode]: !prev[episode] }));
  }, []);

  const reloadProjects = useCallback(async () => {
    const res: { projects?: SavedProject[] } = await fetch(
      `${API}/projects${projectFilter !== "all" ? `?status=${projectFilter}` : ""}`
    ).then((r) => r.json());
    const list = (res.projects || []).filter((p) => p && p.episode);
    setProjects(list);
    setSelectedEpisodes((prev) => {
      const next: Record<string, boolean> = {};
      list.forEach((p) => {
        const ep = p.episode;
        if (!ep) return;
        next[ep] = prev[ep] ?? true;
      });
      return next;
    });
  }, [API, projectFilter]);

  const handlePause = () => {
    if (state === "paused") {
      fetch(`${API}/resume`, { method: "POST" }).then(() => setState("running"));
      return;
    }
    fetch(`${API}/pause`, { method: "POST" }).then(() => setState("paused"));
  };

  const handleStop = () => {
    fetch(`${API}/stop`, { method: "POST" }).then(() => {
      setState("idle");
      setProgress(0);
      setDoneParts(0);
      setTotalParts(0);
      setDoneScenes(0);
      setTotalScenes(0);
    });
  };

  const isRunning = state === "running" || state === "paused";
  const selectedCount = useMemo(() => {
    return projects.filter((p) => p?.episode && selectedEpisodes[p.episode]).length;
  }, [projects, selectedEpisodes]);

  const handleSelectAll = useCallback(() => {
    setSelectedEpisodes((prev) => {
      const next: Record<string, boolean> = { ...prev };
      projects.forEach((p) => {
        const ep = p?.episode;
        if (!ep) return;
        next[ep] = true;
      });
      return next;
    });
  }, [projects]);

  const handleUnselectAll = useCallback(() => {
    setSelectedEpisodes((prev) => {
      const next: Record<string, boolean> = { ...prev };
      projects.forEach((p) => {
        const ep = p?.episode;
        if (!ep) return;
        next[ep] = false;
      });
      return next;
    });
  }, [projects]);

  useEffect(() => {
    const loadWf = async () => {
      try {
        const res: { files?: string[] } = await fetch(`${API}/workflows`).then((r) => r.json());
        const files = (res.files || []).filter(Boolean);
        setWorkflows(files);
        setSelectedWf((prev) => {
          if (prev) return prev;
          const picked =
            files.find((f) => /episode|generate|генер/i.test(f)) ||
            files.find((f) => /gen/i.test(f)) ||
            files[0] ||
            "";
          return picked;
        });
      } catch (e) {
        void e;
      }
    };
    loadWf();
    void reloadProjects();
    const tick = async () => {
      try {
        const p = await fetch(`${API}/progress`).then((r) => r.json());
        const dp = Number(p?.done_parts || 0);
        const tp = Number(p?.total_parts || 0);
        const ds = Number(p?.done_scenes || 0);
        const ts = Number(p?.total_scenes || 0);
        setDoneParts(dp);
        setTotalParts(tp);
        setDoneScenes(ds);
        setTotalScenes(ts);
        const denom = (ts > 0 ? ts : 0) + (tp > 0 ? tp : 0);
        const numer = (ts > 0 ? ds : 0) + (tp > 0 ? dp : 0);
        const pct = denom > 0 ? Math.round((numer / denom) * 100) : 0;
        setProgress(pct);
        if ((ts > 0 && ds >= ts) || (ts === 0 && tp > 0 && dp >= tp)) setState("completed");

        const taskRes: { tasks?: RunnerTask[] } = await fetch(`${API}/tasks`).then((r) => r.json());
        const slice = (taskRes.tasks || []).slice(0, 200);
        const prev = lastTaskStatusRef.current;
        for (const t of slice) {
          const key = t.key;
          const old = prev[key];
          if (t.status === "failed" && old !== "failed") {
            const msg = `Ошибка: ${t.episode} (часть ${t.part})`;
            toast.error(msg);
            sendBrowserNotification("HeyGen Automation", msg);
          }
          prev[key] = t.status;
        }
        lastTaskStatusRef.current = prev;
        setTasks(slice);
      } catch (e) {
        // silent
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [API, projectFilter, reloadProjects, sendBrowserNotification]);

  useEffect(() => {
    if (initialSelectionApplied) return;
    if (projects.length === 0) return;
    const list = projects.map((p) => p.episode).filter((e): e is string => Boolean(e));
    const next: Record<string, boolean> = {};
    if (queryEpisodes.length > 0) {
      list.forEach((ep) => (next[ep] = queryEpisodes.includes(ep)));
    } else {
      list.forEach((ep) => (next[ep] = true));
    }
    setSelectedEpisodes(next);
    setInitialSelectionApplied(true);
  }, [initialSelectionApplied, projects, queryEpisodes]);

  useEffect(() => {
    if (!queryAutostart) return;
    if (autostartTriggered) return;
    if (!initialSelectionApplied) return;
    if (state !== "idle") return;
    const eps = Object.keys(selectedEpisodes).filter((k) => selectedEpisodes[k]);
    if (eps.length === 0) return;
    setAutostartTriggered(true);
    void startEpisodes(eps);
  }, [autostartTriggered, initialSelectionApplied, queryAutostart, selectedEpisodes, startEpisodes, state]);

  return (
    <div className="rounded-xl border border-border shadow-card p-6 space-y-6">
      {/* Controls */}
      <div className="flex items-center gap-3">
        <Select value={selectedWf} onValueChange={setSelectedWf}>
          <SelectTrigger className="w-[240px]">
            <SelectValue placeholder="Файл воркфлоу" />
          </SelectTrigger>
          <SelectContent>
            {workflows.map((f) => (
              <SelectItem key={f} value={f}>{f}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={projectFilter} onValueChange={(v) => setProjectFilter(v)}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Фильтр проектов" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все</SelectItem>
            <SelectItem value="pending">В ожидании</SelectItem>
            <SelectItem value="running">В работе</SelectItem>
            <SelectItem value="completed">Завершён</SelectItem>
            <SelectItem value="failed">Ошибка</SelectItem>
          </SelectContent>
        </Select>
        <Button
          size="lg"
          variant={state === "running" ? "secondary" : "glow"}
          onClick={handleStart}
          disabled={state === "running"}
          className="flex-1"
        >
          <Play className="w-5 h-5 mr-2" />
          {state === "idle"
            ? "ЗАПУСТИТЬ"
            : state === "paused"
              ? "ПРОДОЛЖИТЬ"
              : state === "completed"
                ? "ЗАПУСТИТЬ"
                : "ВЫПОЛНЯЕТСЯ..."}
        </Button>

        <Button
          size="lg"
          variant="outline"
          onClick={handlePause}
          disabled={!isRunning}
          className={cn(state === "paused" && "border-warning text-warning")}
        >
          <Pause className="w-5 h-5" />
        </Button>

        <Button
          size="lg"
          variant="destructive"
          onClick={handleStop}
          disabled={!isRunning}
          className="shadow-lg shadow-destructive/20"
        >
          <Square className="w-5 h-5 mr-2" />
          ОСТАНОВИТЬ
        </Button>
      </div>

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Прогресс пакета</span>
          <span className="font-mono text-foreground">{progress}% выполнено</span>
        </div>
        <Progress value={progress} className="h-3" />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{doneScenes} из {totalScenes} сцен • {doneParts} из {totalParts} частей</span>
          <span>Осталось: —</span>
        </div>
      </div>

      {/* Status Indicator */}
      <div
        className={cn(
          "flex items-center justify-center gap-2 py-3 rounded-lg border",
          state === "running" && "border-primary/30 bg-primary/5 text-primary",
          state === "paused" && "border-warning/30 bg-warning/5 text-warning",
          state === "idle" && "border-border bg-muted/30 text-muted-foreground",
          state === "completed" && "border-success/30 bg-success/5 text-success"
        )}
      >
        {state === "running" && (
          <>
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span className="font-medium">Обработка эпизодов...</span>
          </>
        )}
        {state === "paused" && (
          <>
            <AlertTriangle className="w-4 h-4" />
            <span className="font-medium">Пауза — нажмите «Продолжить»</span>
          </>
        )}
        {state === "idle" && <span className="font-medium">Готово к запуску</span>}
        {state === "completed" && <span className="font-medium">Пакет завершён!</span>}
      </div>

      <div className="rounded-lg border border-border p-4">
        <div className="text-sm font-semibold text-foreground mb-2">Задачи</div>
        <div className="max-h-[240px] overflow-auto scrollbar-thin">
          {tasks.map((t) => (
            <div key={t.key} className="flex items-center justify-between gap-3 py-2 border-b border-border/60 last:border-b-0">
              <div className="min-w-0">
                <div className="text-sm font-mono text-foreground truncate">{t.episode}</div>
                <div className="text-xs text-muted-foreground">part {t.part}</div>
                {t.stage && <div className="text-xs text-muted-foreground truncate">Этап: {t.stage}</div>}
                {t.error && <div className="text-xs text-destructive truncate">Ошибка: {t.error}</div>}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <div
                  className={cn(
                    "text-xs font-medium px-2 py-1 rounded-full",
                    t.status === "queued" && "bg-muted text-muted-foreground",
                    t.status === "running" && "bg-primary/10 text-primary",
                    t.status === "paused" && "bg-warning/10 text-warning",
                    t.status === "success" && "bg-success/10 text-success",
                    t.status === "failed" && "bg-destructive/10 text-destructive",
                    t.status === "stopped" && "bg-muted text-muted-foreground"
                  )}
                >
                  {t.status === "queued"
                    ? "В ОЧЕРЕДИ"
                    : t.status === "running"
                      ? "В РАБОТЕ"
                      : t.status === "paused"
                        ? "ПАУЗА"
                        : t.status === "success"
                          ? "ГОТОВО"
                          : t.status === "failed"
                            ? "ОШИБКА"
                            : "ОСТАНОВЛЕНО"}
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    disabled={t.status !== "running" && t.status !== "paused"}
                    aria-label={t.status === "paused" ? "Продолжить задачу" : "Пауза задачи"}
                    onClick={() =>
                      fetch(`${API}/tasks/${encodeURIComponent(t.episode)}/${t.part}/${t.status === "paused" ? "resume" : "pause"}`, {
                        method: "POST",
                      })
                    }
                  >
                    {t.status === "paused" ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                  </Button>
                  <Button
                    variant="destructive"
                    size="icon"
                    className="h-8 w-8"
                    disabled={t.status !== "running" && t.status !== "paused"}
                    aria-label="Стоп задачи"
                    onClick={() => fetch(`${API}/tasks/${encodeURIComponent(t.episode)}/${t.part}/stop`, { method: "POST" })}
                  >
                    <Square className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="secondary"
                    size="icon"
                    className="h-8 w-8"
                    disabled={t.status !== "failed" && t.status !== "stopped"}
                    aria-label={t.status === "failed" ? "Повторить задачу" : "Запустить задачу"}
                    onClick={() => fetch(`${API}/tasks/${encodeURIComponent(t.episode)}/${t.part}/start`, { method: "POST" })}
                  >
                    {t.status === "failed" ? <RefreshCw className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  </Button>
                </div>
              </div>
            </div>
          ))}
          {tasks.length === 0 && <div className="text-xs text-muted-foreground">Пока нет активных задач</div>}
        </div>
      </div>

      {/* Episodes selection */}
      <div className="rounded-lg border border-border p-4">
        <div className="flex items-center justify-between gap-3 mb-2">
          <div className="text-sm font-semibold text-foreground">Проекты к запуску</div>
          <div className="flex items-center gap-2">
            <div className="text-xs text-muted-foreground">
              {selectedCount} / {projects.length}
            </div>
            <Button variant="outline" size="sm" onClick={handleSelectAll} disabled={projects.length === 0 || isRunning}>
              Выделить все
            </Button>
            <Button variant="outline" size="sm" onClick={handleUnselectAll} disabled={projects.length === 0 || isRunning}>
              Снять выделение
            </Button>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {projects.map((pr) => (
            <div
              key={pr.episode}
              className={cn(
                "p-3 rounded-lg border bg-muted/20 transition-colors cursor-pointer",
                selectedEpisodes[pr.episode] ? "border-primary/30 bg-primary/5" : "hover:bg-muted/30"
              )}
              onClick={() => toggleEpisode(pr.episode)}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-mono text-foreground truncate">{pr.episode}</div>
                  <div className="text-xs text-muted-foreground">{projectStatusRu(pr.status)}</div>
                  {pr.created_at && (
                    <div className="text-xs text-muted-foreground">Добавлено: {formatDateTimeRu(pr.created_at)}</div>
                  )}
                </div>
                <div onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    checked={!!selectedEpisodes[pr.episode]}
                    onCheckedChange={() => toggleEpisode(pr.episode)}
                    className="h-6 w-6 rounded-md [&_svg]:h-5 [&_svg]:w-5"
                  />
                </div>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                <span>{pr.stats?.parts || 0} частей</span>
                <span className="mx-2">•</span>
                <span>{pr.stats?.scenes || pr.stats?.rows || 0} сцен</span>
                <span className="mx-2">•</span>
                <span>{pr.stats?.brolls || 0} broll</span>
              </div>
              {pr.stats?.speakers && pr.stats.speakers.length > 0 && (
                <div className="mt-1 text-xs text-muted-foreground truncate">
                  <span className="text-base font-semibold text-muted-foreground">Спикер: {pr.stats.speakers.join(", ")}</span>
                </div>
              )}
              <div className="mt-3 flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingEpisode(pr.episode);
                  }}
                >
                  Редактировать
                </Button>
                <Button
                  variant="glow"
                  size="icon"
                  aria-label="Запустить"
                  onClick={(e) => {
                    e.stopPropagation();
                    void startEpisodes([pr.episode]);
                  }}
                  disabled={isRunning}
                  className="h-9 w-9"
                >
                  <Play className="w-4 h-4" />
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      variant="destructive"
                      size="icon"
                      aria-label="Удалить"
                      className="h-9 w-9"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Удалить проект?</AlertDialogTitle>
                      <AlertDialogDescription className="font-mono">{pr.episode}</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Отмена</AlertDialogCancel>
                <AlertDialogAction
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        onClick={async () => {
                          try {
                            const res = await fetch(`${API}/projects/${encodeURIComponent(pr.episode)}`, { method: "DELETE" });
                            if (!res.ok) throw new Error(`HTTP ${res.status}`);
                            toast.success("Проект удалён");
                            await reloadProjects();
                          } catch (e) {
                            toast.error("Не удалось удалить проект");
                          }
                        }}
                      >
                        Удалить
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          ))}
          {projects.length === 0 && <div className="text-xs text-muted-foreground">Нет проектов</div>}
        </div>
      </div>
      {editingEpisode && (
        <ProjectEditorDialog
          episodeId={editingEpisode}
          open={!!editingEpisode}
          onOpenChange={handleEditorOpenChange}
          onSaved={reloadProjects}
        />
      )}
    </div>
  );
}
