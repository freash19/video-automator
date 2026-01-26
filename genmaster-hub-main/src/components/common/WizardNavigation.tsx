import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

interface WizardNavigationProps {
  backPath?: string;
  backLabel?: string;
  nextPath?: string;
  nextLabel?: string;
  onNext?: () => void;
  nextDisabled?: boolean;
}

export function WizardNavigation({
  backPath,
  backLabel = "Back",
  nextPath,
  nextLabel = "Next",
  onNext,
  nextDisabled = false,
}: WizardNavigationProps) {
  const navigate = useNavigate();

  const handleNext = () => {
    if (onNext) {
      onNext();
    }
    if (nextPath) {
      navigate(nextPath);
    }
  };

  return (
    <div className="flex items-center justify-between pt-6 mt-6 border-t border-border">
      <div>
        {backPath && (
          <Button variant="outline" onClick={() => navigate(backPath)}>
            <ChevronLeft className="w-4 h-4 mr-1" />
            {backLabel}
          </Button>
        )}
      </div>
      <div>
        {(nextPath || onNext) && (
          <Button onClick={handleNext} disabled={nextDisabled}>
            {nextLabel}
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        )}
      </div>
    </div>
  );
}
