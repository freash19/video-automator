import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { API_BASE_URL, formatDateTimeRu, projectStatusRu } from "@/lib/utils";
import { ProjectEditorDialog } from "@/components/projects/ProjectEditorDialog";
import { useNavigate } from "react-router-dom";
import { Play, Trash2 } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

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

export default function Scripts() {
  const API = API_BASE_URL;
  const navigate = useNavigate();
  const [projects, setProjects] = useState<SavedProject[]>([]);
  const [episodeId, setEpisodeId] = useState("");
  const [editingEpisode, setEditingEpisode] = useState<string | null>(null);
  const [speakerFilter, setSpeakerFilter] = useState<string>("all");

  const speakers = useMemo(() => {
    const s = new Set<string>();
    for (const pr of projects) {
      for (const sp of pr.stats?.speakers || []) {
        const v = String(sp || "").trim();
        if (v) s.add(v);
      }
    }
    return Array.from(s).sort((a, b) => a.localeCompare(b));
  }, [projects]);

  const filteredProjects = useMemo(() => {
    if (speakerFilter === "all") return projects;
    return projects.filter((pr) => (pr.stats?.speakers || []).includes(speakerFilter));
  }, [projects, speakerFilter]);

  const loadProjects = useCallback(async () => {
    try {
      const res = await fetch(`${API}/projects`).then((r) => r.json());
      setProjects(res.projects || []);
    } catch (e) {
      void e;
    }
  }, [API]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Сценарии</h1>
            <Badge variant="secondary" className="text-xs">Проекты</Badge>
          </div>
          <p className="text-muted-foreground">Управление эпизодами: просмотр, редактирование, удаление.</p>
        </div>
      </div>

      <div className="rounded-xl border border-border shadow-card p-4">
        <div className="text-sm font-semibold text-foreground mb-3">Создать проект</div>
        <div className="flex flex-col md:flex-row gap-2">
          <Input
            value={episodeId}
            onChange={(e) => setEpisodeId(e.target.value)}
            placeholder="episode_id (например ep_acupoint_erection)"
            className="flex-1"
          />
          <Button
            onClick={async () => {
              const id = episodeId.trim();
              if (!id) return;
              try {
                const res = await fetch(`${API}/projects/add`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ episodes: [id] }),
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const payload = await res.json();
                if (!payload?.ok) throw new Error("backend returned ok=false");
                toast.success("Проект создан");
                setEpisodeId("");
                await loadProjects();
                setEditingEpisode(id);
              } catch (e) {
                toast.error("Не удалось создать проект");
              }
            }}
          >
            Создать
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-border shadow-card p-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="text-sm font-semibold text-foreground">Все проекты</div>
          <Select value={speakerFilter} onValueChange={setSpeakerFilter}>
            <SelectTrigger className="w-[260px]">
              <SelectValue placeholder="Фильтр по спикеру" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все спикеры</SelectItem>
              {speakers.map((sp) => (
                <SelectItem key={sp} value={sp}>
                  {sp}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filteredProjects.map((pr) => (
            <div key={pr.episode} className="p-3 rounded-lg border bg-muted/20">
              <div className="flex items-center justify-between">
                <div className="text-sm font-mono text-foreground">{pr.episode}</div>
                <div className="text-xs text-muted-foreground">{projectStatusRu(pr.status)}</div>
              </div>
              {pr.created_at && (
                <div className="mt-1 text-xs text-muted-foreground">
                  Добавлено: {formatDateTimeRu(pr.created_at)}
                </div>
              )}
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
                <Button variant="secondary" size="sm" onClick={() => setEditingEpisode(pr.episode)}>
                  Редактировать
                </Button>
                <Button
                  variant="glow"
                  size="icon"
                  aria-label="Запустить"
                  className="h-9 w-9"
                  onClick={() => navigate(`/runner?episodes=${encodeURIComponent(pr.episode)}&autostart=1`)}
                >
                  <Play className="w-4 h-4" />
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" size="icon" aria-label="Удалить" className="h-9 w-9">
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
                            await loadProjects();
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
          {filteredProjects.length === 0 && <div className="text-sm text-muted-foreground">Нет проектов</div>}
        </div>
      </div>

      {editingEpisode && (
        <ProjectEditorDialog
          episodeId={editingEpisode}
          open={!!editingEpisode}
          onOpenChange={(o) => !o && setEditingEpisode(null)}
          onSaved={loadProjects}
        />
      )}
    </div>
  );
}
