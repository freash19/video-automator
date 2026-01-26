import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import Dashboard from "@/pages/Dashboard";
import DataStudio from "@/pages/DataStudio";
import Workflow from "@/pages/Workflow";
import Scripts from "@/pages/Scripts";
import Settings from "@/pages/Settings";
import Runner from "@/pages/Runner";
import Results from "@/pages/Results";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient();

const App = () => {
  useEffect(() => {
    try {
      if (typeof window === "undefined") return;
      if (!("Notification" in window)) return;
      if (Notification.permission !== "default") return;
      void Notification.requestPermission();
    } catch {
      return;
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <AppLayout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/data-studio" element={<DataStudio />} />
              <Route path="/workflow" element={<Workflow />} />
              <Route path="/scripts" element={<Scripts />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/runner" element={<Runner />} />
              <Route path="/results" element={<Results />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </AppLayout>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
