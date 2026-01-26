import { useState } from "react";
import {
  Video,
  Download,
  Trash2,
  Play,
  CheckCircle,
  Film,
  Search,
  Filter,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

interface VideoResult {
  id: string;
  episode: string;
  title: string;
  duration: string;
  size: string;
  createdAt: string;
  status: "ready" | "processing" | "error";
  thumbnail?: string;
}

const sampleVideos: VideoResult[] = [
  { id: "1", episode: "EP_001", title: "Introduction", duration: "2:34", size: "45.2 MB", createdAt: "2 min ago", status: "ready" },
  { id: "2", episode: "EP_002", title: "Getting Started", duration: "3:12", size: "52.8 MB", createdAt: "5 min ago", status: "ready" },
  { id: "3", episode: "EP_003", title: "Advanced Tips", duration: "4:05", size: "68.1 MB", createdAt: "8 min ago", status: "processing" },
  { id: "4", episode: "EP_004", title: "Best Practices", duration: "2:58", size: "48.3 MB", createdAt: "12 min ago", status: "ready" },
  { id: "5", episode: "EP_005", title: "Conclusion", duration: "1:45", size: "32.6 MB", createdAt: "15 min ago", status: "error" },
];

export default function Results() {
  const [videos, setVideos] = useState<VideoResult[]>(sampleVideos);
  const [selected, setSelected] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  const toggleSelect = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selected.length === videos.length) {
      setSelected([]);
    } else {
      setSelected(videos.map((v) => v.id));
    }
  };

  const filteredVideos = videos.filter(
    (v) =>
      v.episode.toLowerCase().includes(searchQuery.toLowerCase()) ||
      v.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const readyCount = videos.filter((v) => v.status === "ready").length;
  const totalSize = videos
    .filter((v) => v.status === "ready")
    .reduce((acc, v) => acc + parseFloat(v.size), 0)
    .toFixed(1);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Results</h1>
          <p className="text-muted-foreground">
            Manage and export your generated videos.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="px-4 py-2 rounded-lg bg-muted/50 flex items-center gap-4">
            <div className="text-center">
              <div className="text-lg font-bold text-foreground">{readyCount}</div>
              <div className="text-xs text-muted-foreground">Ready</div>
            </div>
            <div className="w-px h-8 bg-border" />
            <div className="text-center">
              <div className="text-lg font-bold text-foreground">{totalSize} MB</div>
              <div className="text-xs text-muted-foreground">Total Size</div>
            </div>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search videos..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Button variant="outline" size="icon">
            <Filter className="w-4 h-4" />
          </Button>
        </div>

        {selected.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {selected.length} selected
            </span>
            <Button variant="secondary" size="sm">
              <Film className="w-4 h-4 mr-1" />
              Merge Videos
            </Button>
            <Button variant="secondary" size="sm">
              <Download className="w-4 h-4 mr-1" />
              Download All
            </Button>
            <Button variant="destructive" size="sm">
              <Trash2 className="w-4 h-4 mr-1" />
              Delete
            </Button>
          </div>
        )}
      </div>

      {/* Video Grid */}
      <div className="rounded-xl border border-border shadow-card overflow-hidden">
        {/* Table Header */}
        <div className="flex items-center gap-4 p-4 border-b border-border bg-muted/30 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          <div className="w-8">
            <Checkbox
              checked={selected.length === videos.length && videos.length > 0}
              onCheckedChange={selectAll}
            />
          </div>
          <div className="flex-1">Video</div>
          <div className="w-24 text-center">Duration</div>
          <div className="w-24 text-center">Size</div>
          <div className="w-24 text-center">Status</div>
          <div className="w-32 text-right">Actions</div>
        </div>

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
                  <Video className="w-5 h-5 text-muted-foreground" />
                </div>
                <div>
                  <div className="font-medium text-foreground">{video.episode}</div>
                  <div className="text-sm text-muted-foreground">{video.title}</div>
                </div>
              </div>

              <div className="w-24 text-center font-mono text-sm text-muted-foreground">
                {video.duration}
              </div>

              <div className="w-24 text-center text-sm text-muted-foreground">
                {video.size}
              </div>

              <div className="w-24 flex justify-center">
                <Badge
                  variant="secondary"
                  className={cn(
                    "text-[10px]",
                    video.status === "ready" && "bg-success/10 text-success",
                    video.status === "processing" && "bg-primary/10 text-primary",
                    video.status === "error" && "bg-destructive/10 text-destructive"
                  )}
                >
                  {video.status === "ready" && <CheckCircle className="w-3 h-3 mr-1" />}
                  {video.status}
                </Badge>
              </div>

              <div className="w-32 flex items-center justify-end gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  disabled={video.status !== "ready"}
                >
                  <Play className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  disabled={video.status !== "ready"}
                >
                  <Download className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
