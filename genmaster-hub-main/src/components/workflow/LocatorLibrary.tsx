import { useMemo, useState } from "react";
import { MousePointer, Edit2, Trash2, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface Locator {
  name: string;
  selector: string;
}

interface LocatorLibraryProps {
  locators: Locator[];
  onSelectLocator?: (locator: Locator) => void;
  onCreateLocator?: (locator: Locator) => void;
  onDeleteLocator?: (name: string) => void;
}

export function LocatorLibrary({ locators, onSelectLocator, onCreateLocator, onDeleteLocator }: LocatorLibraryProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createSelector, setCreateSelector] = useState("");
  const [editName, setEditName] = useState<string | null>(null);
  const [editNewName, setEditNewName] = useState("");
  const [editNewSelector, setEditNewSelector] = useState("");

  const filteredLocators = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return (locators || []).filter(
      (loc) => loc.name.toLowerCase().includes(q) || loc.selector.toLowerCase().includes(q)
    );
  }, [locators, searchQuery]);

  const inferType = (selector: string): "css" | "xpath" | "id" => {
    const s = String(selector || "").trim();
    if (s.startsWith("//") || s.startsWith("(//") || s.startsWith("xpath=")) return "xpath";
    if (s.startsWith("#") && !s.includes(" ") && !s.includes(">") && !s.includes(":")) return "id";
    return "css";
  };

  const typeColors = {
    css: "bg-primary/20 text-primary",
    xpath: "bg-warning/20 text-warning",
    id: "bg-success/20 text-success",
  };

  return (
    <div className="rounded-xl border border-border shadow-card h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <MousePointer className="w-5 h-5 text-primary" />
            Locator Library
          </h3>
          <Button
            size="sm"
            onClick={() => {
              setCreateOpen((v) => !v);
              setEditName(null);
            }}
          >
            <Plus className="w-4 h-4 mr-1" />
            Add New
          </Button>
        </div>
        {createOpen && (
          <div className="space-y-2 mb-3">
            <Input
              placeholder="Name (e.g. Generate Button)"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
            />
            <Input
              placeholder='Selector (e.g. "//button[contains(., \\"Generate\\")]" or "#upload-btn")'
              value={createSelector}
              onChange={(e) => setCreateSelector(e.target.value)}
            />
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={() => {
                  const name = createName.trim();
                  const selector = createSelector.trim();
                  if (!name || !selector) return;
                  onCreateLocator?.({ name, selector });
                  setCreateName("");
                  setCreateSelector("");
                  setCreateOpen(false);
                }}
              >
                Save Locator
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setCreateOpen(false);
                  setCreateName("");
                  setCreateSelector("");
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search locators..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Locator List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-thin">
        {filteredLocators.map((locator) => (
          <div
            key={locator.name}
            onClick={() => {
              setSelectedName(locator.name);
              onSelectLocator?.(locator);
            }}
            className={cn(
              "p-3 rounded-lg border cursor-pointer transition-all duration-200",
              selectedName === locator.name
                ? "border-primary bg-primary/5"
                : "border-border hover:border-muted-foreground/50 hover:bg-muted/30"
            )}
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-medium text-foreground">{locator.name}</span>
                <Badge className={cn("text-[10px] px-1.5", typeColors[inferType(locator.selector)])}>
                  {inferType(locator.selector).toUpperCase()}
                </Badge>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={(e) => {
                    e.stopPropagation();
                    setCreateOpen(false);
                    setEditName(locator.name);
                    setEditNewName(locator.name);
                    setEditNewSelector(locator.selector);
                  }}
                >
                  <Edit2 className="w-3 h-3" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteLocator?.(locator.name);
                  }}
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
            {editName === locator.name ? (
              <div className="space-y-2">
                <Input value={editNewName} onChange={(e) => setEditNewName(e.target.value)} />
                <Input value={editNewSelector} onChange={(e) => setEditNewSelector(e.target.value)} />
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      const name = editNewName.trim();
                      const selector = editNewSelector.trim();
                      if (!name || !selector) return;
                      onCreateLocator?.({ name, selector });
                      if (name !== locator.name) {
                        onDeleteLocator?.(locator.name);
                      }
                      setEditName(null);
                    }}
                  >
                    Save
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditName(null);
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <code className="text-xs text-muted-foreground font-mono block truncate">
                {locator.selector}
              </code>
            )}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border bg-muted/20">
        <p className="text-xs text-muted-foreground text-center">
          {filteredLocators.length} locators available
        </p>
      </div>
    </div>
  );
}
