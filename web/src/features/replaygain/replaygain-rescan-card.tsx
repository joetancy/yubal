import {
  getReplayGainRescanStatus,
  startReplayGainRescan,
  type ReplayGainRescanStatus,
} from "@/api/replaygain";
import { showErrorToast, showSuccessToast } from "@/lib/toast";
import { Button, Card, Spinner } from "@heroui/react";
import { AudioLinesIcon, RefreshCwIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

const POLL_INTERVAL_MS = 2000;

export function ReplayGainRescanCard() {
  const [status, setStatus] = useState<ReplayGainRescanStatus | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const previousRunning = useRef<boolean | null>(null);

  const applyStatus = useCallback((next: ReplayGainRescanStatus) => {
    if (previousRunning.current === true && !next.running) {
      if (next.success) {
        showSuccessToast(
          "ReplayGain rescan complete",
          `Library rescanned at ${next.loudness} LUFS.`,
        );
      } else if (next.success === false) {
        showErrorToast(
          "ReplayGain rescan failed",
          "Check the server logs for rsgain details.",
        );
      }
    }

    previousRunning.current = next.running;
    setStatus(next);
  }, []);

  const loadStatus = useCallback(() => {
    void getReplayGainRescanStatus()
      .then(applyStatus)
      .catch((error: unknown) => {
        console.error("Failed to get ReplayGain rescan status:", error);
      });
  }, [applyStatus]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (!status?.running) return;

    const timer = window.setInterval(loadStatus, POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [status?.running, loadStatus]);

  const handleRescan = async () => {
    setIsStarting(true);
    try {
      const next = await startReplayGainRescan();
      previousRunning.current = true;
      setStatus(next);
      showSuccessToast(
        "ReplayGain rescan started",
        `Recalculating the full library at ${next.loudness} LUFS.`,
      );
    } catch (error) {
      console.error("Failed to start ReplayGain rescan:", error);
      showErrorToast(
        "Could not start ReplayGain rescan",
        "A rescan may already be running. Check the server logs for details.",
      );
    } finally {
      setIsStarting(false);
    }
  };

  const running = status?.running ?? false;
  const loudness = status?.loudness ?? -14;

  return (
    <Card className="mb-6 p-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="bg-accent/10 text-accent rounded-lg p-2">
            <AudioLinesIcon className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-foreground font-semibold">ReplayGain</h2>
            <p className="text-muted text-sm">
              {running
                ? `Rescanning the full library at ${loudness} LUFS...`
                : `Recalculate ReplayGain for every track at ${loudness} LUFS.`}
            </p>
          </div>
        </div>

        <Button
          variant="secondary"
          onPress={handleRescan}
          isDisabled={running || isStarting}
          isPending={isStarting}
          className="shrink-0"
        >
          {running || isStarting ? (
            <Spinner color="current" size="sm" />
          ) : (
            <RefreshCwIcon className="h-4 w-4" />
          )}
          {running ? "Rescanning..." : "Rescan ReplayGain"}
        </Button>
      </div>
    </Card>
  );
}
