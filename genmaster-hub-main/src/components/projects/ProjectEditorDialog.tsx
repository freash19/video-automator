import { memo, useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, RefreshCw, Square } from "lucide-react";
import { toast } from "sonner";
import { DataEditor } from "@/components/data-studio/DataEditor";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { API_BASE_URL, cn, formatDateTimeRu, projectStatusRu } from "@/lib/utils";

interface ProjectEditorDialogProps {
  episodeId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: () => void;
}

interface DataRow {
  id: string;
  selected: boolean;
  data: Record<string, string>;
}

type TaskStatus = "queued" | "running" | "paused" | "success" | "failed" | "stopped";
interface ProjectTask {
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

function toStringValue(v: unknown): string {
  if (v === null || v === undefined) return "";
  return String(v);
}

function formatTs(ts: unknown): string {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return "";
  try {
    return new Date(n * 1000).toLocaleString();
  } catch {
    return "";
  }
}

export const ProjectEditorDialog = memo(function ProjectEditorDialog({
  episodeId,
  open,
  onOpenChange,
  onSaved,
}: ProjectEditorDialogProps) {
  const API = API_BASE_URL;
  const onOpenChangeRef = useRef(onOpenChange);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [projectStatus, setProjectStatus] = useState<string>("");
  const [createdAt, setCreatedAt] = useState<string>("");
  const [stats, setStats] = useState<{
    parts?: number;
    scenes?: number;
    rows?: number;
    speakers?: string[];
    brolls?: number;
    template_url?: string | null;
  } | null>(null);
  const [rows, setRows] = useState<DataRow[]>([]);
  const [tasks, setTasks] = useState<ProjectTask[]>([]);

  useEffect(() => {
    onOpenChangeRef.current = onOpenChange;
  }, [onOpenChange]);

  useEffect(() => {
    const load = async () => {
      if (!open) return;
      setLoading(true);
      try {
        const res = await fetch(`${API}/projects/${encodeURIComponent(episodeId)}?include_data=1`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = await res.json();
        const pr = payload?.project;
        setStats(payload?.stats || null);
        const data: Array<Record<string, unknown>> = Array.isArray(pr?.data) ? pr.data : [];
        const mapped: DataRow[] = data.map((r) => ({
          id: crypto.randomUUID(),
          selected: false,
          data: Object.fromEntries(Object.entries(r || {}).map(([k, v]) => [k, toStringValue(v)])),
        }));
        setProjectStatus(String(pr?.status || ""));
        setCreatedAt(String(pr?.created_at || ""));
        setRows(mapped);
      } catch (e) {
        toast.error("Не удалось загрузить проект");
        onOpenChangeRef.current(false);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [API, episodeId, open]);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    const load = async () => {
      setLoadingTasks(true);
      try {
        const res: { tasks?: ProjectTask[] } = await fetch(
          `${API}/tasks?episode=${encodeURIComponent(episodeId)}`
        ).then((r) => r.json());
        if (!alive) return;
        setTasks(res.tasks || []);
      } catch {
        if (!alive) return;
        setTasks([]);
      } finally {
        if (alive) setLoadingTasks(false);
      }
    };
    void load();
    const id = setInterval(load, 1000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [API, episodeId, open]);

  const columns = useMemo(() => {
    const ordered: string[] = [];
    const seen = new Set<string>();
    for (const row of rows) {
      for (const key of Object.keys(row.data || {})) {
        if (seen.has(key)) continue;
        seen.add(key);
        ordered.push(key);
      }
    }
    return ordered;
  }, [rows]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = { status: projectStatus || "pending", data: rows.map((r) => r.data) };
      const res = await fetch(`${API}/projects/${encodeURIComponent(episodeId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast.success("Проект сохранён");
      onSaved?.();
      onOpenChange(false);
    } catch (e) {
      toast.error("Не удалось сохранить проект");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-6xl w-[95vw]"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle className="font-mono">{episodeId}</DialogTitle>
        </DialogHeader>
        <div className="text-xs text-muted-foreground">
          <span>Статус: {projectStatusRu(projectStatus)}</span>
          {createdAt ? (
            <>
              <span className="mx-2">•</span>
              <span>Добавлено: {formatDateTimeRu(createdAt)}</span>
            </>
          ) : null}
        </div>
        {stats && (
          <div className="text-xs text-muted-foreground">
            <span>{stats.parts || 0} частей</span>
            <span className="mx-2">•</span>
            <span>{stats.scenes || stats.rows || 0} сцен</span>
            <span className="mx-2">•</span>
            <span>{stats.brolls || 0} broll</span>
            {stats.speakers && stats.speakers.length > 0 && (
              <>
                <span className="mx-2">•</span>
                <span className="truncate">Спикер: {stats.speakers.join(", ")}</span>
              </>
            )}
          </div>
        )}
        {stats?.template_url && (
          <a
            className="text-xs text-muted-foreground truncate hover:underline"
            href={stats.template_url}
            target="_blank"
            rel="noreferrer"
          >
            {stats.template_url}
          </a>
        )}
        <div className="rounded-lg border border-border p-4">
          <div className="text-sm font-semibold text-foreground mb-2">Задачи проекта</div>
          {loadingTasks ? (
            <div className="text-xs text-muted-foreground">Загрузка…</div>
          ) : (
            <div className="max-h-[220px] overflow-auto scrollbar-thin">
              {tasks.map((t) => (
                <div
                  key={t.key}
                  className="flex items-start justify-between gap-3 py-2 border-b border-border/60 last:border-b-0"
                >
                  <div className="min-w-0">
                    <div className="text-xs text-muted-foreground">Часть {t.part}</div>
                    {t.stage && <div className="text-xs text-muted-foreground truncate">Этап: {t.stage}</div>}
                    {t.error && <div className="text-xs text-destructive truncate">Ошибка: {t.error}</div>}
                    <div className="text-[11px] text-muted-foreground">
                      {t.started_at ? `Старт: ${formatTs(t.started_at)}` : "Старт: —"}
                      <span className="mx-2">•</span>
                      {t.finished_at ? `Финиш: ${formatTs(t.finished_at)}` : "Финиш: —"}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      Сцены: {Number(t.scene_done || 0)} / {Number(t.scene_total || 0)}
                    </div>
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
                        onClick={() =>
                          fetch(`${API}/tasks/${encodeURIComponent(t.episode)}/${t.part}/stop`, {
                            method: "POST",
                          })
                        }
                      >
                        <Square className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="secondary"
                        size="icon"
                        className="h-8 w-8"
                        disabled={t.status !== "failed" && t.status !== "stopped"}
                        aria-label={t.status === "failed" ? "Повторить задачу" : "Запустить задачу"}
                        onClick={() =>
                          fetch(`${API}/tasks/${encodeURIComponent(t.episode)}/${t.part}/start`, {
                            method: "POST",
                          })
                        }
                      >
                        {t.status === "failed" ? <RefreshCw className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
              {tasks.length === 0 && <div className="text-xs text-muted-foreground">Нет задач по проекту</div>}
            </div>
          )}
        </div>
        {loading ? (
          <div className="text-sm text-muted-foreground">Загрузка…</div>
        ) : (
          <DataEditor data={rows} columns={columns} onDataChange={setRows} />
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Закрыть
          </Button>
          <Button onClick={handleSave} disabled={saving || loading}>
            Сохранить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
});
