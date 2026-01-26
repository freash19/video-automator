import { useEffect, useRef, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Trash2, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

interface DataRow {
  id: string;
  selected: boolean;
  data: Record<string, string>;
}

interface DataEditorProps {
  data: DataRow[];
  columns: string[];
  onDataChange: (data: DataRow[]) => void;
}

export function DataEditor({ data, columns, onDataChange }: DataEditorProps) {
  const [editingCell, setEditingCell] = useState<{ rowId: string; column: string } | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const getColumnClass = (column: string) => {
    if (column === "part_idx" || column === "scene_idx") {
      return "w-[3ch] min-w-[3ch]";
    }
    if (column === "text") {
      return "min-w-[63ch]";
    }
    return "min-w-[12ch]";
  };

  useEffect(() => {
    if (!editingCell) return;
    inputRef.current?.focus({ preventScroll: true });
  }, [editingCell]);

  const handleCellChange = (rowId: string, column: string, value: string) => {
    const newData = data.map((row) =>
      row.id === rowId ? { ...row, data: { ...row.data, [column]: value } } : row
    );
    onDataChange(newData);
  };

  const handleSelectRow = (rowId: string) => {
    const newData = data.map((row) =>
      row.id === rowId ? { ...row, selected: !row.selected } : row
    );
    onDataChange(newData);
  };

  const handleSelectAll = () => {
    const allSelected = data.every((row) => row.selected);
    const newData = data.map((row) => ({ ...row, selected: !allSelected }));
    onDataChange(newData);
  };

  const handleDeleteSelected = () => {
    const newData = data.filter((row) => !row.selected);
    onDataChange(newData);
  };

  const handleAddRow = () => {
    const newRow: DataRow = {
      id: crypto.randomUUID(),
      selected: false,
      data: columns.reduce((acc, col) => ({ ...acc, [col]: "" }), {}),
    };
    onDataChange([...data, newRow]);
  };

  const selectedCount = data.filter((row) => row.selected).length;

  return (
    <div className="rounded-xl border border-border shadow-card overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-muted/30">
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">
            {data.length} строк • {selectedCount} выбрано
          </span>
        </div>
        <div className="flex items-center gap-2">
          {selectedCount > 0 && (
            <Button variant="destructive" size="sm" onClick={handleDeleteSelected}>
              <Trash2 className="w-4 h-4 mr-1" />
              Удалить выбранные
            </Button>
          )}
          <Button variant="secondary" size="sm" onClick={handleAddRow}>
            <Plus className="w-4 h-4 mr-1" />
            Добавить строку
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="max-h-[360px] overflow-auto scrollbar-thin">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/20">
              <th className="w-12 p-2">
                <Checkbox
                  checked={data.length > 0 && data.every((row) => row.selected)}
                  onCheckedChange={handleSelectAll}
                />
              </th>
              <th className="w-12 p-2 text-xs font-medium text-muted-foreground text-left">
                #
              </th>
              {columns.map((column) => (
                <th
                  key={column}
                  className={cn(
                    "p-2 text-xs font-medium text-muted-foreground text-left uppercase tracking-wider",
                    getColumnClass(column)
                  )}
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, index) => (
              <tr
                key={row.id}
                className={cn(
                  "border-b border-border transition-colors",
                  row.selected ? "bg-primary/5" : "hover:bg-muted/30"
                )}
              >
                <td className="p-2">
                  <Checkbox
                    checked={row.selected}
                    onCheckedChange={() => handleSelectRow(row.id)}
                  />
                </td>
                <td className="p-2 text-xs font-mono text-muted-foreground">
                  {index + 1}
                </td>
                {columns.map((column) => (
                  <td key={`${row.id}-${column}`} className={cn("p-1", getColumnClass(column))}>
                    {editingCell?.rowId === row.id && editingCell?.column === column ? (
                      <Input
                        ref={inputRef}
                        value={row.data[column] || ""}
                        onChange={(e) => handleCellChange(row.id, column, e.target.value)}
                        onBlur={() => setEditingCell(null)}
                        onKeyDown={(e) => e.key === "Enter" && setEditingCell(null)}
                        className={cn("h-7 text-sm bg-background", getColumnClass(column))}
                      />
                    ) : (
                      <div
                        onClick={() => setEditingCell({ rowId: row.id, column })}
                        className={cn(
                          "px-2 py-1 text-sm cursor-text hover:bg-muted/50 rounded min-h-[28px] flex items-center",
                          getColumnClass(column)
                        )}
                      >
                        {row.data[column] || (
                          <span className="text-muted-foreground/50 italic">Пусто</span>
                        )}
                      </div>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="text-muted-foreground mb-2">Данных пока нет</div>
          <p className="text-sm text-muted-foreground/70">
            Загрузите CSV или вставьте данные, чтобы начать
          </p>
        </div>
      )}
    </div>
  );
}
