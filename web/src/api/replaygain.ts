import { basePath } from "@/lib/base-path";

export interface ReplayGainRescanStatus {
  running: boolean;
  loudness: number;
  success: boolean | null;
}

const RESCAN_URL = `${basePath}/api/replaygain/rescan`;

async function parseStatus(response: Response): Promise<ReplayGainRescanStatus> {
  if (!response.ok) {
    throw new Error("ReplayGain rescan request failed");
  }
  return (await response.json()) as ReplayGainRescanStatus;
}

export async function getReplayGainRescanStatus(): Promise<ReplayGainRescanStatus> {
  return parseStatus(await fetch(RESCAN_URL));
}

export async function startReplayGainRescan(): Promise<ReplayGainRescanStatus> {
  return parseStatus(
    await fetch(RESCAN_URL, {
      method: "POST",
    }),
  );
}
