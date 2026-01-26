import { useEffect, useState, useCallback } from "react";
import {
  Video,
  Download,
  Trash2,
  Play,
  CheckCircle,
  Film,
  Search,
  RefreshCw,
  Loader2,
  ExternalLink,
  Clock,
  Calendar,
  HardDrive,
  AlertCircle,
  ArrowUp,
  ArrowDown,
  GripVertical,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { cn, API_BASE_URL } from "@/lib/utils";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface VideoResult {
  id: string;
  title: string;
  created_at: string;
  duration: string;
  download_url: string | null;
  status: string;
  file_path: string | null;
  size: string | null;
}

interface VideosResponse {
  videos: VideoResult[];
  last_scraped: string | null;
}

interface MergeTask {
  id: string;
  status: "downloading" | "merging" | "completed" | "error";
  progress: string;
  downloadedCount: number;
  totalToDownload: number;
  outputPath?: string;
  outputSize?: string;
  duration?: string;
  error?: string;
}

interface MergeResult {
  outputPath: string;
  outputName: string;
  size: string;
  duration: string;
  videoCount: number;
  videoTitles: string[];
}

// Helper to persist merge state across page navigation
const MERGE_TASK_KEY = "heygen_merge_task";
const MERGE_RESULT_KEY = "heygen_merge_result";

const loadPersistedMergeTask = (): MergeTask | null => {
  try {
    const stored = localStorage.getItem(MERGE_TASK_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
};

const persistMergeTask = (task: MergeTask | null) => {
  try {
    if (task) {
      localStorage.setItem(MERGE_TASK_KEY, JSON.stringify(task));
    } else {
      localStorage.removeItem(MERGE_TASK_KEY);
    }
  } catch {
    // ignore
  }
};

const loadPersistedMergeResult = (): MergeResult | null => {
  try {
    const stored = localStorage.getItem(MERGE_RESULT_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
};

const persistMergeResult = (result: MergeResult | null) => {
  try {
    if (result) {
      localStorage.setItem(MERGE_RESULT_KEY, JSON.stringify(result));
    } else {
      localStorage.removeItem(MERGE_RESULT_KEY);
    }
  } catch {
    // ignore
  }
};

export default function Results() {
  const API = API_BASE_URL;
  const [videos, setVideos] = useState<VideoResult[]>([]);
  const [lastScraped, setLastScraped] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [scraping, setScraping] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [merging, setMerging] = useState(false);
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);
  const [mergeOrder, setMergeOrder] = useState<string[]>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [videoToDelete, setVideoToDelete] = useState<string | null>(null);
  const [outputName, setOutputName] = useState("");
  const [mergeTask, setMergeTaskState] = useState<MergeTask | null>(loadPersistedMergeTask);
  const [mergeResult, setMergeResultState] = useState<MergeResult | null>(loadPersistedMergeResult);
  const [resultDialogOpen, setResultDialogOpen] = useState(false);

  // Wrapper to persist merge task
  const setMergeTask = (taskOrUpdater: MergeTask | null | ((prev: MergeTask | null) => MergeTask | null)) => {
    setMergeTaskState(prev => {
      const newTask = typeof taskOrUpdater === 'function' ? taskOrUpdater(prev) : taskOrUpdater;
      persistMergeTask(newTask);
      return newTask;
    });
  };

  // Wrapper to persist merge result
  const setMergeResult = (result: MergeResult | null) => {
    persistMergeResult(result);
    setMergeResultState(result);
  };

  // Show result dialog if we have a result on mount
  useEffect(() => {
    if (mergeResult && !resultDialogOpen) {
      setResultDialogOpen(true);
    }
  }, []);

  const loadVideos = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/videos`);
      const data: VideosResponse = await res.json();
      setVideos(data.videos || []);
      setLastScraped(data.last_scraped);
    } catch (e) {
      console.error("Failed to load videos:", e);
      toast.error("Не удалось загрузить список видео");
    } finally {
      setLoading(false);
    }
  }, [API]);

  useEffect(() => {
    loadVideos();
  }, [loadVideos]);

  const handleScrape = async () => {
    setScraping(true);
    try {
      const res = await fetch(`${API}/videos/scrape`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_count: 30 }),
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Scrape failed");
      }
      
      const data = await res.json();
      toast.success(`Найдено ${data.count} видео`);
      await loadVideos();
    } catch (e) {
      console.error("Scrape failed:", e);
      toast.error(`Ошибка сканирования: ${e instanceof Error ? e.message : "Неизвестная ошибка"}`);
    } finally {
      setScraping(false);
    }
  };

  const handleDownload = async (videoId: string) => {
    setDownloading(videoId);
    try {
      const res = await fetch(`${API}/videos/${videoId}/download`, {
        method: "POST",
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Download failed");
      }
      
      const data = await res.json();
      toast.success(`Видео скачано: ${data.file_path}`);
      await loadVideos();
    } catch (e) {
      console.error("Download failed:", e);
      toast.error(`Ошибка скачивания: ${e instanceof Error ? e.message : "Неизвестная ошибка"}`);
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadSelected = async () => {
    if (selected.length === 0) return;
    
    setDownloading("batch");
    try {
      const res = await fetch(`${API}/videos/download-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_ids: selected }),
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Batch download failed");
      }
      
      const data = await res.json();
      toast.success(`Скачано ${data.downloaded} видео`);
      if (data.errors && data.errors.length > 0) {
        toast.warning(`Ошибки: ${data.errors.length}`);
      }
      await loadVideos();
    } catch (e) {
      console.error("Batch download failed:", e);
      toast.error(`Ошибка: ${e instanceof Error ? e.message : "Неизвестная ошибка"}`);
    } finally {
      setDownloading(null);
    }
  };

  const handleMerge = async () => {
    if (selected.length < 2) {
      toast.error("Выберите минимум 2 видео для склейки");
      return;
    }
    
    // Initialize merge order with selected videos in current order
    setMergeOrder([...selected]);
    setOutputName(`merged_${new Date().toISOString().slice(0,10)}.mp4`);
    setMergeDialogOpen(true);
  };

  const moveMergeItem = (index: number, direction: "up" | "down") => {
    const newOrder = [...mergeOrder];
    const newIndex = direction === "up" ? index - 1 : index + 1;
    
    if (newIndex < 0 || newIndex >= newOrder.length) return;
    
    [newOrder[index], newOrder[newIndex]] = [newOrder[newIndex], newOrder[index]];
    setMergeOrder(newOrder);
  };

  const confirmMerge = async () => {
    setMergeDialogOpen(false);
    setMerging(true);
    
    const finalOutputName = outputName || `merged_${Date.now()}.mp4`;
    
    // Check which videos need downloading
    const selectedVideos = videos.filter(v => mergeOrder.includes(v.id));
    const notDownloaded = selectedVideos.filter(v => !v.file_path);
    
    // Initialize task tracking
    const taskId = `merge_${Date.now()}`;
    setMergeTask({
      id: taskId,
      status: notDownloaded.length > 0 ? "downloading" : "merging",
      progress: notDownloaded.length > 0 ? "Скачивание видео..." : "Подготовка к склейке...",
      downloadedCount: 0,
      totalToDownload: notDownloaded.length,
    });
    
    try {
      // Download missing videos first
      if (notDownloaded.length > 0) {
        for (let i = 0; i < notDownloaded.length; i++) {
          const video = notDownloaded[i];
          setMergeTask(prev => prev ? {
            ...prev,
            progress: `Скачивание ${i + 1}/${notDownloaded.length}: ${video.title}`,
            downloadedCount: i,
          } : null);
          
          try {
            const res = await fetch(`${API}/videos/${video.id}/download`, {
              method: "POST",
            });
            
            if (!res.ok) {
              const err = await res.json().catch(() => ({}));
              throw new Error(err.detail || `Не удалось скачать: ${video.title}`);
            }
            
            // Update count after successful download
            setMergeTask(prev => prev ? {
              ...prev,
              downloadedCount: i + 1,
            } : null);
          } catch (downloadErr) {
            console.error(`Download error for ${video.title}:`, downloadErr);
            throw new Error(`Не удалось скачать: ${video.title}`);
          }
        }
        
        // Reload videos to get updated file paths
        await loadVideos();
        
        setMergeTask(prev => prev ? {
          ...prev,
          status: "merging",
          progress: "Все видео скачаны. Начинаем склейку...",
          downloadedCount: notDownloaded.length,
        } : null);
      }
      
      // Now merge
      setMergeTask(prev => prev ? {
        ...prev,
        status: "merging",
        progress: `Склеивание ${mergeOrder.length} видео...`,
      } : null);
      
      const res = await fetch(`${API}/videos/merge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_ids: mergeOrder,
          output_name: finalOutputName,
        }),
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Merge failed");
      }
      
      const data = await res.json();
      
      // Show result
      setMergeTask(prev => prev ? {
        ...prev,
        status: "completed",
        progress: "Готово!",
        outputPath: data.output_path,
        outputSize: data.size,
        duration: data.duration,
      } : null);
      
      // Get titles of merged videos
      const mergedVideoTitles = mergeOrder
        .map(id => videos.find(v => v.id === id)?.title || id)
        .filter(Boolean);
      
      setMergeResult({
        outputPath: data.output_path,
        outputName: finalOutputName,
        size: data.size || "—",
        duration: data.duration || "—",
        videoCount: mergeOrder.length,
        videoTitles: mergedVideoTitles,
      });
      
      setResultDialogOpen(true);
      toast.success(`Видео объединены!`);
      setSelected([]);
      setMergeOrder([]);
      
    } catch (e) {
      console.error("Merge failed:", e);
      setMergeTask(prev => prev ? {
        ...prev,
        status: "error",
        progress: "Ошибка",
        error: e instanceof Error ? e.message : "Неизвестная ошибка",
      } : null);
      toast.error(`Ошибка: ${e instanceof Error ? e.message : "Неизвестная ошибка"}`);
    } finally {
      setMerging(false);
      // Clear task after delay
      setTimeout(() => setMergeTask(null), 5000);
    }
  };

  const handleDelete = async (videoId: string) => {
    setVideoToDelete(videoId);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!videoToDelete) return;
    
    try {
      const res = await fetch(`${API}/videos/${videoToDelete}`, {
        method: "DELETE",
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Delete failed");
      }
      
      toast.success("Видео удалено");
      setSelected(prev => prev.filter(id => id !== videoToDelete));
      await loadVideos();
    } catch (e) {
      console.error("Delete failed:", e);
      toast.error(`Ошибка удаления: ${e instanceof Error ? e.message : "Неизвестная ошибка"}`);
    } finally {
      setDeleteDialogOpen(false);
      setVideoToDelete(null);
    }
  };

  const handleDeleteSelected = async () => {
    if (selected.length === 0) return;
    
    for (const id of selected) {
      try {
        await fetch(`${API}/videos/${id}`, { method: "DELETE" });
      } catch (e) {
        console.error(`Failed to delete ${id}:`, e);
      }
    }
    
    toast.success(`Удалено ${selected.length} видео`);
    setSelected([]);
    await loadVideos();
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selected.length === filteredVideos.length) {
      setSelected([]);
    } else {
      setSelected(filteredVideos.map((v) => v.id));
    }
  };

  // Separate merged videos from source videos
  const mergedVideos = videos.filter((v) => (v as VideoResult & { merged?: boolean }).merged === true);
  const sourceVideos = videos.filter((v) => (v as VideoResult & { merged?: boolean }).merged !== true);
  
  const filteredVideos = sourceVideos.filter(
    (v) =>
      v.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      v.created_at?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const readyCount = sourceVideos.filter((v) => v.file_path).length;
  const totalCount = sourceVideos.length;
  const mergedCount = mergedVideos.length;

  const getStatusBadge = (video: VideoResult) => {
    if (video.file_path) {
      return (
        <Badge variant="secondary" className="bg-success/10 text-success text-[10px]">
          <CheckCircle className="w-3 h-3 mr-1" />
          скачано
        </Badge>
      );
    }
    if (video.status === "ready") {
      return (
        <Badge variant="secondary" className="bg-primary/10 text-primary text-[10px]">
          <Video className="w-3 h-3 mr-1" />
          готово
        </Badge>
      );
    }
    if (video.status === "draft") {
      return (
        <Badge variant="secondary" className="bg-muted text-muted-foreground text-[10px]">
          черновик
        </Badge>
      );
    }
    return (
      <Badge variant="secondary" className="bg-warning/10 text-warning text-[10px]">
        <Loader2 className="w-3 h-3 mr-1 animate-spin" />
        обработка
      </Badge>
    );
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    try {
      if (dateStr.includes("г.") || dateStr.includes("января") || dateStr.includes("февраля")) {
        return dateStr;
      }
      const date = new Date(dateStr);
      return date.toLocaleDateString("ru-RU", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Видео</h1>
          <p className="text-muted-foreground">
            Управляйте и выгружайте сгенерированные видео из HeyGen.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="px-4 py-2 rounded-lg bg-muted/50 flex items-center gap-4">
            <div className="text-center">
              <div className="text-lg font-bold text-foreground">{readyCount}</div>
              <div className="text-xs text-muted-foreground">Скачано</div>
            </div>
            <div className="w-px h-8 bg-border" />
            <div className="text-center">
              <div className="text-lg font-bold text-foreground">{totalCount}</div>
              <div className="text-xs text-muted-foreground">Всего</div>
            </div>
            {mergedCount > 0 && (
              <>
                <div className="w-px h-8 bg-border" />
                <div className="text-center">
                  <div className="text-lg font-bold text-success">{mergedCount}</div>
                  <div className="text-xs text-muted-foreground">Склеено</div>
                </div>
              </>
            )}
          </div>
          <Button
            onClick={handleScrape}
            disabled={scraping}
            className="gap-2"
          >
            {scraping ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            Сканировать HeyGen
          </Button>
        </div>
      </div>

      {/* Last scraped info */}
      {lastScraped && (
        <div className="text-sm text-muted-foreground flex items-center gap-2">
          <Clock className="w-4 h-4" />
          Последнее сканирование: {formatDate(lastScraped)}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Поиск видео..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Button variant="outline" size="icon" onClick={loadVideos} disabled={loading}>
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          </Button>
        </div>

        {selected.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {selected.length} выбрано
            </span>
            <Button 
              variant="secondary" 
              size="sm"
              onClick={handleMerge}
              disabled={merging || selected.length < 2}
            >
              {merging ? (
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              ) : (
                <Film className="w-4 h-4 mr-1" />
              )}
              Склеить видео
            </Button>
            <Button 
              variant="secondary" 
              size="sm"
              onClick={handleDownloadSelected}
              disabled={downloading === "batch"}
            >
              {downloading === "batch" ? (
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              ) : (
                <Download className="w-4 h-4 mr-1" />
              )}
              Скачать все
            </Button>
            <Button 
              variant="destructive" 
              size="sm"
              onClick={handleDeleteSelected}
            >
              <Trash2 className="w-4 h-4 mr-1" />
              Удалить
            </Button>
          </div>
        )}
      </div>

      {/* Merged Videos Section */}
      {mergedVideos.length > 0 && (
        <div className="rounded-xl border border-border shadow-card overflow-hidden bg-success/5">
          <div className="px-4 py-3 border-b border-border bg-success/10 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Film className="w-5 h-5 text-success" />
              <span className="font-semibold text-foreground">Склеенные видео</span>
              <Badge variant="secondary" className="ml-2">{mergedCount}</Badge>
            </div>
          </div>
          <div className="divide-y divide-border">
            {mergedVideos.map((video) => (
              <div
                key={video.id}
                className="flex items-center gap-4 p-4 transition-colors hover:bg-muted/30"
              >
                <div className="w-10 h-10 rounded-lg bg-success/20 flex items-center justify-center">
                  <Film className="w-5 h-5 text-success" />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-foreground truncate">{video.title}</div>
                  <div className="text-xs text-muted-foreground truncate font-mono">{video.file_path}</div>
                </div>

                <div className="w-24 text-center text-sm text-muted-foreground">
                  {video.duration || "-"}
                </div>

                <div className="w-20 text-center text-sm text-muted-foreground">
                  {video.size || "-"}
                </div>

                <div className="w-32 text-center text-sm text-muted-foreground">
                  {formatDate(video.created_at)}
                </div>

                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={async () => {
                      if (video.file_path) {
                        try {
                          await fetch(`${API}/reveal-in-finder`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ path: video.file_path }),
                          });
                          toast.success("Открыто в Finder");
                        } catch {
                          toast.info(`Путь: ${video.file_path}`);
                        }
                      }
                    }}
                  >
                    <ExternalLink className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => toast.info(`Файл: ${video.file_path}`)}
                  >
                    <Play className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive"
                    onClick={() => handleDelete(video.id)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Video Grid */}
      <div className="rounded-xl border border-border shadow-card overflow-hidden">
        {/* Table Header */}
        <div className="flex items-center gap-4 p-4 border-b border-border bg-muted/30 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          <div className="w-8">
            <Checkbox
              checked={selected.length === filteredVideos.length && filteredVideos.length > 0}
              onCheckedChange={selectAll}
            />
          </div>
          <div className="flex-1">Видео</div>
          <div className="w-32 text-center">Дата</div>
          <div className="w-20 text-center">Длительность</div>
          <div className="w-20 text-center">Размер</div>
          <div className="w-24 text-center">Статус</div>
          <div className="w-32 text-right">Действия</div>
        </div>

        {/* Loading state */}
        {loading && videos.length === 0 && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Empty state */}
        {!loading && videos.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Video className="w-12 h-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">Нет видео</p>
            <p className="text-sm">Нажмите "Сканировать HeyGen" чтобы найти видео</p>
          </div>
        )}

        {/* Video Rows */}
        <div className="divide-y divide-border">
          {filteredVideos.map((video) => (
            <div
              key={video.id}
              className={cn(
                "flex items-center gap-4 p-4 transition-colors hover:bg-muted/30",
                selected.includes(video.id) && "bg-primary/5"
              )}
            >
              <div className="w-8">
                <Checkbox
                  checked={selected.includes(video.id)}
                  onCheckedChange={() => toggleSelect(video.id)}
                />
              </div>

              <div className="flex-1 flex items-center gap-3">
                <div className="w-16 h-10 rounded-lg bg-muted flex items-center justify-center">
                  {video.file_path ? (
                    <CheckCircle className="w-5 h-5 text-success" />
                  ) : (
                    <Video className="w-5 h-5 text-muted-foreground" />
                  )}
                </div>
                <div className="min-w-0">
                  <div className="font-medium text-foreground truncate">{video.title}</div>
                  {video.file_path && (
                    <div className="text-xs text-muted-foreground truncate">{video.file_path}</div>
                  )}
                </div>
              </div>

              <div className="w-32 text-center text-sm text-muted-foreground flex items-center justify-center gap-1">
                <Calendar className="w-3 h-3" />
                <span className="truncate">{formatDate(video.created_at)}</span>
              </div>

              <div className="w-20 text-center font-mono text-sm text-muted-foreground">
                {video.duration || "-"}
              </div>

              <div className="w-20 text-center text-sm text-muted-foreground flex items-center justify-center gap-1">
                {video.size ? (
                  <>
                    <HardDrive className="w-3 h-3" />
                    {video.size}
                  </>
                ) : (
                  "-"
                )}
              </div>

              <div className="w-24 flex justify-center">
                {getStatusBadge(video)}
              </div>

              <div className="w-32 flex items-center justify-end gap-1">
                {video.file_path && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => {
                      // Open file location or play
                      toast.info(`Файл: ${video.file_path}`);
                    }}
                  >
                    <Play className="w-4 h-4" />
                  </Button>
                )}
                {video.download_url && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => window.open(video.download_url!, "_blank")}
                  >
                    <ExternalLink className="w-4 h-4" />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  disabled={downloading === video.id || video.status === "draft"}
                  onClick={() => handleDownload(video.id)}
                >
                  {downloading === video.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  onClick={() => handleDelete(video.id)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Merge Dialog */}
      <Dialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Склеить видео</DialogTitle>
            <DialogDescription>
              Измените порядок видео кнопками или оставьте как есть.
              Настройки качества берутся из раздела Конфигурация.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            {/* Output filename */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Имя выходного файла</label>
              <Input
                value={outputName}
                onChange={(e) => setOutputName(e.target.value)}
                placeholder="merged_video.mp4"
              />
            </div>
            
            {/* Video order */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Порядок склейки ({mergeOrder.length} видео)</label>
              <div className="space-y-1 max-h-60 overflow-y-auto border rounded-lg p-2">
                {mergeOrder.map((id, index) => {
                  const video = videos.find(v => v.id === id);
                  return (
                    <div 
                      key={id} 
                      className="flex items-center gap-2 p-2 bg-muted/50 rounded hover:bg-muted transition-colors"
                    >
                      <GripVertical className="w-4 h-4 text-muted-foreground" />
                      <span className="text-sm font-mono text-muted-foreground w-6">{index + 1}.</span>
                      <span className="text-sm truncate flex-1">{video?.title || id}</span>
                      <span className="text-xs text-muted-foreground">{video?.duration}</span>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          disabled={index === 0}
                          onClick={() => moveMergeItem(index, "up")}
                        >
                          <ArrowUp className="w-3 h-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          disabled={index === mergeOrder.length - 1}
                          onClick={() => moveMergeItem(index, "down")}
                        >
                          <ArrowDown className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setMergeDialogOpen(false)}>
              Отмена
            </Button>
            <Button onClick={confirmMerge} disabled={mergeOrder.length < 2}>
              <Film className="w-4 h-4 mr-2" />
              Склеить {mergeOrder.length} видео
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить видео?</AlertDialogTitle>
            <AlertDialogDescription>
              Это действие нельзя отменить. Видео будет удалено из списка,
              а скачанный файл будет удален с диска.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Merge Progress Indicator */}
      {mergeTask && (
        <div className="fixed bottom-6 right-6 w-80 bg-background border border-border rounded-xl shadow-lg p-4 z-50">
          <div className="flex items-start gap-3">
            {mergeTask.status === "downloading" && (
              <Download className="w-5 h-5 text-primary animate-pulse mt-0.5" />
            )}
            {mergeTask.status === "merging" && (
              <Loader2 className="w-5 h-5 text-primary animate-spin mt-0.5" />
            )}
            {mergeTask.status === "completed" && (
              <CheckCircle className="w-5 h-5 text-success mt-0.5" />
            )}
            {mergeTask.status === "error" && (
              <AlertCircle className="w-5 h-5 text-destructive mt-0.5" />
            )}
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm">
                {mergeTask.status === "downloading" && "Скачивание видео"}
                {mergeTask.status === "merging" && "Монтаж видео"}
                {mergeTask.status === "completed" && "Монтаж завершён"}
                {mergeTask.status === "error" && "Ошибка монтажа"}
              </div>
              <div className="text-xs text-muted-foreground truncate mt-0.5">
                {mergeTask.progress}
              </div>
              {mergeTask.status === "downloading" && mergeTask.totalToDownload > 0 && (
                <div className="mt-2">
                  <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-primary transition-all duration-300"
                      style={{ width: `${(mergeTask.downloadedCount / mergeTask.totalToDownload) * 100}%` }}
                    />
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {mergeTask.downloadedCount} / {mergeTask.totalToDownload}
                  </div>
                </div>
              )}
              {mergeTask.error && (
                <div className="text-xs text-destructive mt-1">{mergeTask.error}</div>
              )}
            </div>
            {/* Close button */}
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 -mt-1 -mr-1"
              onClick={() => setMergeTask(null)}
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Merge Result Dialog */}
      <Dialog open={resultDialogOpen} onOpenChange={(open) => {
        setResultDialogOpen(open);
        if (!open) {
          // Clear result when dialog is closed
          setMergeResult(null);
        }
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-success" />
              Монтаж завершён
            </DialogTitle>
            <DialogDescription>
              Видео успешно объединены
            </DialogDescription>
          </DialogHeader>
          
          {mergeResult && (
            <div className="space-y-4">
              <div className="bg-muted/50 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <Film className="w-10 h-10 text-primary" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-lg">{mergeResult.outputName}</div>
                    <div className="text-sm text-muted-foreground truncate font-mono">{mergeResult.outputPath}</div>
                  </div>
                </div>
                
                <div className="grid grid-cols-3 gap-4 pt-3 border-t border-border">
                  <div className="text-center">
                    <div className="text-lg font-bold text-foreground">{mergeResult.videoCount}</div>
                    <div className="text-xs text-muted-foreground">Видео</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold text-foreground">{mergeResult.duration}</div>
                    <div className="text-xs text-muted-foreground">Длительность</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold text-foreground">{mergeResult.size}</div>
                    <div className="text-xs text-muted-foreground">Размер</div>
                  </div>
                </div>

                {/* List of merged videos */}
                {mergeResult.videoTitles && mergeResult.videoTitles.length > 0 && (
                  <div className="pt-3 border-t border-border">
                    <div className="text-xs font-medium text-muted-foreground mb-2">Объединённые эпизоды:</div>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {mergeResult.videoTitles.map((title, idx) => (
                        <div key={idx} className="text-sm flex items-center gap-2">
                          <span className="text-muted-foreground font-mono text-xs">{idx + 1}.</span>
                          <span className="truncate">{title}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
          
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => {
              setResultDialogOpen(false);
              setMergeResult(null);
            }}>
              Закрыть
            </Button>
            <Button 
              variant="secondary"
              onClick={async () => {
                if (mergeResult?.outputPath) {
                  try {
                    // Call backend to reveal in Finder
                    await fetch(`${API}/reveal-in-finder`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ path: mergeResult.outputPath }),
                    });
                    toast.success("Открыто в Finder");
                  } catch {
                    // Fallback: just show path
                    toast.info(`Путь: ${mergeResult.outputPath}`);
                  }
                }
              }}
            >
              <ExternalLink className="w-4 h-4 mr-2" />
              Открыть в Finder
            </Button>
            <Button onClick={() => {
              if (mergeResult?.outputPath) {
                toast.info(`Файл готов: ${mergeResult.outputPath}`);
              }
              setResultDialogOpen(false);
              setMergeResult(null);
            }}>
              <Play className="w-4 h-4 mr-2" />
              Воспроизвести
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}