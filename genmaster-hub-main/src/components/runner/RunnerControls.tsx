import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Play, Square, Pause, RefreshCw, AlertTriangle, Trash2, Monitor } from "lucide-react";
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
  report_details?: Record<string, Array<Record<string, unknown>>> | null;
}

interface TaskStatusDetails {
  steps?: Array<{
    name: string;
    status: string;
    error_message?: string | null;
  }>;
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
  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>({});
  const [taskStatuses, setTaskStatuses] = useState<Record<string, TaskStatusDetails>>({});
  const [pendingDelete, setPendingDelete] = useState<{ episode: string; expiresAt: number } | null>(null);
  const pendingDeleteTimerRef = useRef<number | null>(null);
  const [profiles, setProfiles] = useState<string[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<string>("ask");
  const [browserEngine, setBrowserEngine] = useState<"chrome" | "chromium">("chrome");

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

  const updateBrowserConfig = useCallback(async () => {
    try {
      const cfg = await fetch(`${API}/config`).then((r) => r.json());
      const profiles = cfg?.profiles || {};
      const profile = profiles[selectedProfile] as { cdp_url?: string; browser_type?: string } | undefined;
      
      let chromeCdpUrl = cfg?.chrome_cdp_url || "http://localhost:9222";
      let forceEmbedded = browserEngine === "chromium";
      
      // Use profile settings if available
      if (profile && selectedProfile) {
        const profileBrowserType = profile.browser_type || (profile.cdp_url ? "chrome" : "chromium");
        
        if (profileBrowserType === "chrome" && profile.cdp_url) {
          chromeCdpUrl = profile.cdp_url;
          forceEmbedded = false;
        } else if (profileBrowserType === "chromium") {
          forceEmbedded = true;
        } else {
          // Fallback: use manual selection
          forceEmbedded = browserEngine === "chromium";
          if (profile.cdp_url) {
            chromeCdpUrl = profile.cdp_url;
          }
        }
      } else {
        // No profile selected - use manual selection
        forceEmbedded = browserEngine === "chromium";
      }
      
      await fetch(`${API}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_to_use: selectedProfile || (Object.keys(profiles)[0] || ""),
          browser: "chrome",
          chrome_cdp_url: chromeCdpUrl,
          force_embedded_browser: forceEmbedded,
          multilogin_cdp_url: "",
        }),
      });
    } catch {
      // ignore
    }
  }, [API, browserEngine, selectedProfile]);

  const startEpisodes = useCallback(
    async (episodes: string[]) => {
      const eps = episodes.filter(Boolean);
      if (eps.length === 0) {
        toast.error("Не выбраны проекты для запуска");
        return;
      }
      try {
        await updateBrowserConfig();
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
    [API, selectedWf, updateBrowserConfig]
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
        next[ep] = prev[ep] ?? false;
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

  const handleOpenBrowser = useCallback(async () => {
    try {
      await updateBrowserConfig();
      const res = await fetch(`${API}/browser/open`, { method: "POST" });
      if (!res.ok) {
        const t = await res.text().catch(() => "");
        throw new Error(t || `HTTP ${res.status}`);
      }
      toast.success("Браузер открыт");
    } catch (e) {
      toast.error("Не удалось открыть браузер");
    }
  }, [API, updateBrowserConfig]);

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

  const clearPendingDelete = useCallback(() => {
    if (pendingDeleteTimerRef.current) {
      window.clearTimeout(pendingDeleteTimerRef.current);
      pendingDeleteTimerRef.current = null;
    }
    setPendingDelete(null);
  }, []);

  const executeDelete = useCallback(
    async (episode: string) => {
      try {
        const res = await fetch(`${API}/projects/${encodeURIComponent(episode)}`, { method: "DELETE" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        toast.success("Проект удалён");
        await reloadProjects();
      } catch (e) {
        toast.error("Не удалось удалить проект");
      }
    },
    [API, reloadProjects]
  );

  const scheduleDelete = useCallback(
    (episode: string) => {
      clearPendingDelete();
      setPendingDelete({ episode, expiresAt: Date.now() + 5000 });
      pendingDeleteTimerRef.current = window.setTimeout(() => {
        pendingDeleteTimerRef.current = null;
        setPendingDelete(null);
        void executeDelete(episode);
      }, 5000);
      toast.success("Удаление запланировано на 5 секунд");
    },
    [clearPendingDelete, executeDelete]
  );

  const projectStatusBadgeClass = useCallback((status: string) => {
    const s = String(status || "").toLowerCase();
    if (s === "completed" || s === "success") return "bg-success/15 text-success border-success/30";
    if (s === "running") return "bg-primary/15 text-primary border-primary/30";
    if (s === "failed") return "bg-destructive/15 text-destructive border-destructive/30";
    if (s === "pending") return "bg-muted text-muted-foreground border-border";
    return "bg-muted text-muted-foreground border-border";
  }, []);

  const summarizeReport = useCallback((task: RunnerTask) => {
    const rep = task.report;
    const labels: Record<string, string> = {
      validation_missing: "несоответствия",
      broll_skipped: "b-roll пропущен",
      broll_no_results: "b-roll без результатов",
      broll_errors: "ошибки b-roll",
      manual_intervention: "вмешательство",
    };
    if (!rep || typeof rep !== "object") {
      if (task.status === "success") return { text: "Отчёт: ошибок нет", tone: "ok" };
      if (task.status === "failed") return { text: "Отчёт: нет данных", tone: "error" };
      return { text: "Отчёт: —", tone: "muted" };
    }
    const items = Object.entries(rep)
      .map(([k, v]) => ({
        key: k,
        count: Number(v ?? 0),
      }))
      .filter((i) => Number.isFinite(i.count) && i.count > 0);
    if (items.length === 0) {
      return { text: "Отчёт: ошибок нет", tone: "ok" };
    }
    const parts = items.map((i) => `${labels[i.key] || i.key}: ${i.count}`);
    return { text: `Отчёт: ${parts.join(", ")}`, tone: "error" };
  }, []);

  const extractSceneList = useCallback((items?: Array<Record<string, unknown>>) => {
    if (!items || items.length === 0) return "";
    const scenes = items
      .map((i) => (typeof i?.scene_idx === "number" || typeof i?.scene_idx === "string" ? String(i.scene_idx) : ""))
      .filter(Boolean);
    return scenes.join(", ");
  }, []);

  const renderReportDetails = useCallback(
    (task: RunnerTask) => {
      const details = task.report_details;
      if (!details) return null;
      const missing = extractSceneList(details.validation_missing);
      const brollSkipped = extractSceneList(details.broll_skipped);
      const brollNoResults = extractSceneList(details.broll_no_results);
      const brollErrors = extractSceneList(details.broll_errors);
      const manual = extractSceneList(details.manual_intervention);
      const lines = [
        missing ? `Незаполненные сцены: ${missing}` : "",
        brollNoResults ? `B-roll без результатов: ${brollNoResults}` : "",
        brollErrors ? `B-roll ошибки: ${brollErrors}` : "",
        brollSkipped ? `B-roll пропущен: ${brollSkipped}` : "",
        manual ? `Ручные подтверждения: ${manual}` : "",
      ].filter(Boolean);
      if (lines.length === 0) return null;
      return (
        <div className="text-xs text-muted-foreground space-y-0.5">
          {lines.map((line) => (
            <div key={line} className="truncate">{line}</div>
          ))}
        </div>
      );
    },
    [extractSceneList]
  );

  const toggleTaskDetails = useCallback(
    async (task: RunnerTask) => {
      setExpandedTasks((prev) => ({ ...prev, [task.key]: !prev[task.key] }));
      if (expandedTasks[task.key]) return;
      if (taskStatuses[task.key]) return;
      try {
        const res = await fetch(`${API}/task/${encodeURIComponent(task.key)}/status`);
        if (!res.ok) return;
        const data = (await res.json()) as TaskStatusDetails;
        setTaskStatuses((prev) => ({ ...prev, [task.key]: data }));
      } catch (e) {
        void e;
      }
    },
    [API, expandedTasks, taskStatuses]
  );

  useEffect(() => {
    const loadWf = async () => {
      try {
        const cfg = await fetch(`${API}/config`).then((r) => r.json());
        const prof = cfg?.profiles || {};
        const profileNames = Object.keys(prof || {}).filter(Boolean);
        setProfiles(profileNames);
        
        const currentProfile = String(cfg?.profile_to_use || "").trim();
        const validProfile = profileNames.includes(currentProfile) ? currentProfile : (profileNames[0] || "");
        setSelectedProfile(validProfile);
        
        // Determine browser engine from profile or config
        if (validProfile && prof[validProfile]) {
          const profile = prof[validProfile] as { cdp_url?: string; browser_type?: string };
          if (profile.browser_type === "chromium") {
            setBrowserEngine("chromium");
          } else if (profile.browser_type === "chrome" || profile.cdp_url) {
            setBrowserEngine("chrome");
          } else {
            setBrowserEngine("chromium");
          }
        } else {
          setBrowserEngine(cfg?.force_embedded_browser ? "chromium" : "chrome");
        }

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
        const hasActive = slice.some((t) => ["running", "paused", "queued"].includes(t.status));
        if (!hasActive && state !== "idle" && state !== "completed") {
          setState("idle");
        }
      } catch (e) {
        // silent
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [API, projectFilter, reloadProjects, sendBrowserNotification, state]);

  useEffect(() => {
    return () => {
      if (pendingDeleteTimerRef.current) {
        window.clearTimeout(pendingDeleteTimerRef.current);
      }
    };
  }, []);

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
      <div className="flex items-start gap-6">
        <div className="flex-1 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <Button
              size="lg"
              variant={state === "running" ? "secondary" : "glow"}
              onClick={handleStart}
              disabled={state === "running"}
              className="min-w-[200px]"
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
              variant="destructive"
              onClick={handleStop}
              disabled={!isRunning}
              className="shadow-lg shadow-destructive/20"
            >
              <Square className="w-5 h-5 mr-2" />
              ОСТАНОВИТЬ
            </Button>

            <Button
              size="icon"
              variant="outline"
              onClick={handleOpenBrowser}
              aria-label="Открыть браузер"
              data-testid="open-browser-button"
            >
              <Monitor className="w-5 h-5" />
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
          </div>

          <div className="flex items-center gap-3">
            <Select value={selectedWf} onValueChange={setSelectedWf}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Файл воркфлоу" />
              </SelectTrigger>
              <SelectContent>
                {workflows.map((f) => (
                  <SelectItem key={f} value={f}>{f}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedProfile} onValueChange={(v) => {
              setSelectedProfile(v);
              // Auto-update browser engine based on profile
              fetch(`${API}/config`).then((r) => r.json()).then((config) => {
                const profile = config?.profiles?.[v];
                if (profile?.cdp_url) {
                  setBrowserEngine("chrome");
                } else {
                  setBrowserEngine("chromium");
                }
              }).catch(() => {});
            }}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Профиль браузера" />
              </SelectTrigger>
              <SelectContent>
                {profiles.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select 
              value={browserEngine} 
              onValueChange={(v) => setBrowserEngine(v as "chrome" | "chromium")}
            >
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Браузер" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="chrome">Chrome (CDP)</SelectItem>
                <SelectItem value="chromium">Chromium (встроенный)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="shrink-0">
          <div
            className={cn(
              "w-[280px] flex items-center justify-center gap-2 py-3 rounded-lg border",
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
        </div>
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

      {/* Status Indicator moved to top-right */}

      <div className="rounded-lg border border-border p-4">
        <div className="text-sm font-semibold text-foreground mb-2">Задачи</div>
        <div className="max-h-[240px] overflow-auto scrollbar-thin">
          {tasks.map((t) => (
            <div key={t.key} className="flex items-center justify-between gap-3 py-2 border-b border-border/60 last:border-b-0">
              <div className="min-w-0">
                <div className="text-sm font-mono text-foreground truncate">{t.episode}</div>
                <div className="text-xs text-muted-foreground">часть {t.part}</div>
                {t.stage && <div className="text-xs text-muted-foreground truncate">Этап: {t.stage}</div>}
                {t.error && <div className="text-xs text-destructive truncate">Ошибка: {t.error}</div>}
                {(() => {
                  const rep = summarizeReport(t);
                  if (!rep?.text) return null;
                  return (
                    <div
                      className={cn(
                        "text-xs truncate",
                        rep.tone === "ok" && "text-success",
                        rep.tone === "error" && "text-destructive",
                        rep.tone === "muted" && "text-muted-foreground"
                      )}
                    >
                      {rep.text}
                    </div>
                  );
                })()}
                {renderReportDetails(t)}
                {expandedTasks[t.key] && (() => {
                  const detail = taskStatuses[t.key];
                  const steps = detail?.steps || [];
                  const failed = steps.filter((s) => s.status === "failed");
                  const skipped = steps.filter((s) => s.status === "skipped");
                  if (failed.length === 0 && skipped.length === 0) return null;
                  return (
                    <div className="text-xs text-muted-foreground space-y-0.5">
                      {failed.length > 0 && (
                        <div className="text-destructive truncate">
                          Шаги с ошибкой: {failed.map((s) => s.error_message ? `${s.name} (${s.error_message})` : s.name).join(", ")}
                        </div>
                      )}
                      {skipped.length > 0 && (
                        <div className="truncate">Пропущенные шаги: {skipped.map((s) => s.name).join(", ")}</div>
                      )}
                    </div>
                  );
                })()}
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
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="task-details-toggle"
                  onClick={() => void toggleTaskDetails(t)}
                >
                  {expandedTasks[t.key] ? "Скрыть" : "Детали"}
                </Button>
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
            <Select value={projectFilter} onValueChange={(v) => setProjectFilter(v)}>
              <SelectTrigger className="w-[180px]">
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
        {pendingDelete && (
          <div className="mb-3 flex items-center justify-between gap-3 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning-foreground">
            <div className="truncate">
              Проект будет удалён через 5 секунд: <span className="font-mono">{pendingDelete.episode}</span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                clearPendingDelete();
                toast.success("Удаление отменено");
              }}
            >
              Отменить
            </Button>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {projects.map((pr) => (
            <div
              key={pr.episode}
              className={cn(
                "p-3 rounded-lg border bg-muted/20 transition-colors cursor-pointer relative",
                selectedEpisodes[pr.episode] ? "border-primary/30 bg-primary/5" : "hover:bg-muted/30",
                (pr.status === "completed" || pr.status === "success") && "border-success/40 bg-success/10"
              )}
              onClick={() => toggleEpisode(pr.episode)}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-mono text-foreground truncate">{pr.episode}</div>
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
                  <span className="text-base font-semibold text-foreground">Спикер: {pr.stats.speakers.join(", ")}</span>
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
                          scheduleDelete(pr.episode);
                        }}
                      >
                        Удалить
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
              <div
                data-testid="project-status-badge"
                className={cn(
                  "absolute bottom-2 right-2 text-[11px] font-medium px-2 py-1 rounded-full border",
                  projectStatusBadgeClass(pr.status)
                )}
              >
                {projectStatusRu(pr.status)}
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
