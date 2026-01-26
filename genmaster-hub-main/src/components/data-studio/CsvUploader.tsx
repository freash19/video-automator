import { useState, useCallback } from "react";
import { Upload, FileText, ClipboardPaste, X, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { API_BASE_URL, cn } from "@/lib/utils";

interface CsvUploaderProps {
  onDataParsed: (data: Record<string, string>[], columns: string[]) => void;
}

export function CsvUploader({ onDataParsed }: CsvUploaderProps) {
  const [dragActive, setDragActive] = useState(false);
  const [csvText, setCsvText] = useState("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [parseStatus, setParseStatus] = useState<"idle" | "success" | "error">("idle");
  const API = API_BASE_URL;

  const parseCsv = (content: string) => {
    const lines = content.trim().split("\n");
    if (lines.length < 2) {
      setParseStatus("error");
      return;
    }

    const header = lines[0];
    const delim = (header.match(/;/g)?.length || 0) > (header.match(/,/g)?.length || 0) ? ";" : ",";
    const columns = header.split(delim).map((col) => col.trim().replace(/"/g, ""));
    const data = lines.slice(1).map((line) => {
      const values = line.split(delim).map((val) => val.trim().replace(/"/g, ""));
      return columns.reduce((acc, col, i) => ({ ...acc, [col]: values[i] || "" }), {});
    });

    setParseStatus("success");
    onDataParsed(data, columns);
  };

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      handleFile(file);
    }
  }, []);

  const handleFile = (file: File) => {
    setUploadedFile(file);
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      parseCsv(content);
    };
    reader.readAsText(file);
    const form = new FormData();
    form.append("file", file);
    fetch(`${API}/csv/upload`, { method: "POST", body: form })
      .then(() => setParseStatus("success"))
      .catch(() => setParseStatus("error"));
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleTextParse = () => {
    if (csvText.trim()) {
      parseCsv(csvText);
      const form = new FormData();
      form.append("text", csvText);
      fetch(`${API}/csv/text`, { method: "POST", body: form })
        .then(() => setParseStatus("success"))
        .catch(() => setParseStatus("error"));
    }
  };

  const clearUpload = () => {
    setUploadedFile(null);
    setParseStatus("idle");
    setCsvText("");
  };

  return (
    <div className="rounded-xl border border-border p-6 shadow-card">
      <h3 className="text-lg font-semibold text-foreground mb-4">Импорт данных</h3>

      <Tabs defaultValue="upload" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="upload" className="flex items-center gap-2">
            <Upload className="w-4 h-4" />
            Загрузить CSV
          </TabsTrigger>
          <TabsTrigger value="paste" className="flex items-center gap-2">
            <ClipboardPaste className="w-4 h-4" />
            Вставить текст
          </TabsTrigger>
        </TabsList>

        <TabsContent value="upload" className="space-y-4">
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={cn(
              "relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200",
              dragActive
                ? "border-primary bg-primary/5"
                : "border-border hover:border-muted-foreground/50",
              uploadedFile && parseStatus === "success" && "border-success bg-success/5"
            )}
          >
            {uploadedFile ? (
              <div className="flex items-center justify-center gap-3">
                <div className="flex items-center gap-2">
                  <FileText className="w-5 h-5 text-primary" />
                  <span className="font-medium text-foreground">{uploadedFile.name}</span>
                  {parseStatus === "success" && (
                    <CheckCircle className="w-4 h-4 text-success" />
                  )}
                </div>
                <Button variant="ghost" size="icon" onClick={clearUpload}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <>
                <Upload className="w-10 h-10 mx-auto mb-4 text-muted-foreground" />
                <p className="text-foreground font-medium mb-1">
                  Перетащите CSV сюда
                </p>
                <p className="text-sm text-muted-foreground mb-4">
                  или нажмите для выбора файла
                </p>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileInput}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
              </>
            )}
          </div>
        </TabsContent>

        <TabsContent value="paste" className="space-y-4">
          <Textarea
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            placeholder="Вставьте CSV как текст...&#10;&#10;Пример:&#10;episode,title,script&#10;EP_001,Intro,Привет мир"
            className="min-h-[200px] font-mono text-sm"
          />
          <Button onClick={handleTextParse} disabled={!csvText.trim()}>
            Разобрать CSV
          </Button>
        </TabsContent>
      </Tabs>
    </div>
  );
}
