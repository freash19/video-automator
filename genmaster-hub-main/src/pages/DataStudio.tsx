import { useCallback, useEffect, useMemo, useState } from "react";
import { CsvUploader } from "@/components/data-studio/CsvUploader";
import { DataEditor } from "@/components/data-studio/DataEditor";
import { WizardNavigation } from "@/components/common/WizardNavigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ProjectEditorDialog } from "@/components/projects/ProjectEditorDialog";
import { toast } from "sonner";
import { API_BASE_URL, formatDateTimeRu, projectStatusRu } from "@/lib/utils";
import { Play, Trash2 } from "lucide-react";
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
import { useNavigate } from "react-router-dom";

interface DataRow {
  id: string;
  selected: boolean;
  data: Record<string, string>;
}

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

// Sample data for demo
const sampleData: DataRow[] = [];

const sampleColumns: string[] = [];

export default function DataStudio() {
  const [data, setData] = useState<DataRow[]>(sampleData);
  const [columns, setColumns] = useState<string[]>(sampleColumns);
  const API = API_BASE_URL;
  const navigate = useNavigate();
  const [editingEpisode, setEditingEpisode] = useState<string | null>(null);
  const [uploaderKey, setUploaderKey] = useState(0);

  const handleDataParsed = (parsedData: Record<string, string>[], parsedColumns: string[]) => {
    const newData: DataRow[] = parsedData.map((row) => ({
      id: crypto.randomUUID(),
      selected: true,
      data: row,
    }));
    setData(newData);
    setColumns(parsedColumns);
  };

  const selectedCount = data.filter((row) => row.selected).length;
  const [savedProjects, setSavedProjects] = useState<SavedProject[]>([]);

  const fileStats = useMemo(() => {
    const rows = data.map((r) => r.data || {});
    const selectedRows = data.filter((r) => r.selected).map((r) => r.data || {});
    const episodes = new Set<string>();
    const speakers = new Set<string>();
    const partsVals: number[] = [];
    let scenes = 0;
    let brolls = 0;
    let templateUrl: string | null = null;

    for (const r of rows) {
      const ep = String(r["episode_id"] || r["episode"] || "").trim();
      if (ep) episodes.add(ep);
      const sp = String(r["speaker"] || "").trim();
      if (sp) speakers.add(sp);
      const partRaw = r["part_idx"] ?? r["part"];
      const partNum = partRaw === undefined || partRaw === null ? NaN : Number(partRaw);
      if (Number.isFinite(partNum)) partsVals.push(Math.trunc(partNum));
      const sceneRaw = r["scene_idx"] ?? r["scene"] ?? r["scene_number"];
      if (sceneRaw !== undefined && sceneRaw !== null && String(sceneRaw).trim()) scenes += 1;
      const b = r["broll_query"] ?? r["brolls"];
      if (b !== undefined && b !== null && String(b).trim()) brolls += 1;
      if (!templateUrl) {
        const t = r["template_url"];
        if (t !== undefined && t !== null && String(t).trim()) templateUrl = String(t).trim();
      }
    }
    if (rows.length > 0 && scenes === 0) scenes = rows.length;
    const parts = partsVals.length ? Math.max(...partsVals) : 0;

    const selectedEpisodes = new Set<string>();
    for (const r of selectedRows) {
      const ep = String(r["episode_id"] || r["episode"] || "").trim();
      if (ep) selectedEpisodes.add(ep);
    }

    return {
      rows: rows.length,
      selectedRows: selectedRows.length,
      episodes: episodes.size,
      selectedEpisodes: selectedEpisodes.size,
      parts,
      scenes,
      speakers: Array.from(speakers),
      brolls,
      templateUrl,
    };
  }, [data]);

  const handleAddProjects = useCallback(async () => {
    const episodes = Array.from(
      new Set(
        data
          .filter((r) => r.selected)
          .map((r) => r.data["episode"] || r.data["episode_id"])
          .filter(Boolean),
      ),
    );

    if (!episodes.length) return;

    try {
      const res = await fetch(`${API}/projects/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          episodes,
          rows: data.filter((r) => r.selected).map((r) => r.data),
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const payload = await res.json();
      if (!payload?.ok) {
        throw new Error("backend returned ok=false");
      }

      setSavedProjects(payload.projects || []);
      setData([]);
      setColumns([]);
      setUploaderKey((k) => k + 1);
      toast.success("Проекты добавлены");
    } catch (e) {
      toast.error("Не удалось добавить проекты (бэкенд недоступен)");
    }
  }, [API, data]);

  const loadProjects = useCallback(async () => {
    try {
      const res = await fetch(`${API}/projects`).then((r) => r.json());
      setSavedProjects(res.projects || []);
    } catch (e) {
      void e;
    }
  }, [API]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Студия данных</h1>
            <Badge variant="secondary" className="text-xs">Шаг 1</Badge>
          </div>
          <p className="text-muted-foreground">
            Импорт и подготовка данных эпизодов для автоматизации.
          </p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-muted/50">
          <span className="text-sm text-muted-foreground">Выбрано:</span>
          <span className="text-lg font-bold text-primary">{selectedCount}</span>
          <span className="text-sm text-muted-foreground">/ {data.length}</span>
        </div>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <CsvUploader key={uploaderKey} onDataParsed={handleDataParsed} />
        </div>
        <div className="lg:col-span-2">
          <div className="mt-4 rounded-xl border border-border p-4 shadow-card">
            <div className="text-sm font-semibold text-foreground mb-2">Проекты</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {savedProjects.map((pr) => (
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
              {savedProjects.length === 0 && <div className="text-sm text-muted-foreground">Нет проектов</div>}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border p-4 shadow-card">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-foreground">Предпросмотр файла</div>
            <div className="mt-1 text-xs text-muted-foreground">
              <span>{fileStats.rows} строк</span>
              <span className="mx-2">•</span>
              <span>{fileStats.episodes} эпизодов</span>
              <span className="mx-2">•</span>
              <span>{fileStats.parts} частей</span>
              <span className="mx-2">•</span>
              <span>{fileStats.scenes} сцен</span>
              <span className="mx-2">•</span>
              <span>{fileStats.brolls} broll</span>
              <span className="mx-2">•</span>
              <span>{fileStats.selectedRows} выбрано</span>
            </div>
            {fileStats.speakers.length > 0 && (
              <div className="mt-2 text-sm font-medium text-muted-foreground truncate">
                Спикер: {fileStats.speakers.join(", ")}
              </div>
            )}
            {fileStats.templateUrl && (
              <a
                className="mt-1 block text-xs text-muted-foreground truncate hover:underline"
                href={fileStats.templateUrl}
                target="_blank"
                rel="noreferrer"
              >
                {fileStats.templateUrl}
              </a>
            )}
          </div>
          <Button
            variant="glow"
            onClick={handleAddProjects}
            disabled={selectedCount === 0}
            className="shrink-0"
          >
            Добавить проекты
          </Button>
        </div>
      </div>

      <DataEditor data={data} columns={columns} onDataChange={setData} />
      {editingEpisode && (
        <ProjectEditorDialog
          episodeId={editingEpisode}
          open={!!editingEpisode}
          onOpenChange={(o) => !o && setEditingEpisode(null)}
          onSaved={loadProjects}
        />
      )}

      {/* Wizard Navigation */}
      <WizardNavigation
        backPath="/"
        backLabel="Панель"
        nextPath="/workflow"
        nextLabel="Настроить воркфлоу"
        nextDisabled={selectedCount === 0}
      />
    </div>
  );
}
