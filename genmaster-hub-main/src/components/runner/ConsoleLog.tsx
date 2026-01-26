import { useEffect, useRef, useState } from "react";
import { Terminal, Trash2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { API_BASE_URL, cn } from "@/lib/utils";

interface LogEntry {
  id: string;
  timestamp: string;
  level: "info" | "success" | "warning" | "error" | "debug";
  message: string;
  worker?: number;
}

const sampleLogs: LogEntry[] = [];

const levelStyles = {
  info: "text-muted-foreground",
  success: "text-success",
  warning: "text-warning",
  error: "text-destructive",
  debug: "text-purple-400",
};

const levelPrefix = {
  info: "INFO",
  success: "✓ OK",
  warning: "WARN",
  error: "ERR!",
  debug: "DBG",
};

export function ConsoleLog() {
  const [logs, setLogs] = useState<LogEntry[]>(sampleLogs);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const API = API_BASE_URL;

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  useEffect(() => {
    const tick = async () => {
      try {
        const raw: Array<{ level?: string; msg?: string }> = await fetch(`${API}/logs?limit=2000`).then((r) => r.json());
        const now = () => new Date().toLocaleTimeString();
        const mapped: LogEntry[] = raw.map((e, idx: number) => ({
          id: String(idx),
          timestamp: now(),
          level: e.level === "step" ? "debug" : (String(e.msg || "").startsWith("error:") ? "error" : (String(e.msg || "").startsWith("finish:") ? "success" : "info")),
          message: e.msg,
          worker: 1,
        }));
        setLogs(mapped);
      } catch (e) {
        // silent
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  const clearLogs = () => setLogs([]);

  const downloadLogs = () => {
    const content = logs
      .map((log) => `[${log.timestamp}] [W${log.worker}] [${levelPrefix[log.level]}] ${log.message}`)
      .join("\n");
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `automation-log-${new Date().toISOString().split("T")[0]}.txt`;
    a.click();
  };

  return (
    <div className="rounded-xl border border-border shadow-card flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-primary" />
          <span className="font-medium text-sm text-foreground">Консоль</span>
          <span className="text-xs text-muted-foreground">({logs.length} записей)</span>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={downloadLogs}>
            <Download className="w-3 h-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={clearLogs}>
            <Trash2 className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Console */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 terminal-bg font-mono text-xs space-y-0.5 scrollbar-thin"
        onScroll={(e) => {
          const el = e.currentTarget;
          const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
          setAutoScroll(isAtBottom);
        }}
      >
        {logs.map((log) => (
          <div key={log.id} className="flex items-start gap-2 hover:bg-muted/20 px-1 py-0.5 rounded">
            <span className="text-muted-foreground/60 shrink-0">{log.timestamp}</span>
            <span className="text-muted-foreground/40 shrink-0">[Р{log.worker}]</span>
            <span className={cn("shrink-0 w-12", levelStyles[log.level])}>
              {levelPrefix[log.level]}
            </span>
            <span className={cn("flex-1", levelStyles[log.level])}>{log.message}</span>
          </div>
        ))}
        <div className="flex items-center gap-1 text-primary animate-pulse">
          <span className="inline-block w-2 h-4 bg-primary" />
        </div>
      </div>
    </div>
  );
}
