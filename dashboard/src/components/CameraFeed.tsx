import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ESP32_STREAM_URL } from "@/lib/config";

type StreamStatus = "loading" | "live" | "error";

export default function CameraFeed() {
  const [status, setStatus] = useState<StreamStatus>("loading");
  const [streamKey, setStreamKey] = useState(0);

  function retryStream() {
    setStatus("loading");
    setStreamKey((k) => k + 1);
  }

  return (
    <Card
      className="border-border p-6"
      style={{ background: "var(--gradient-card)", boxShadow: "var(--shadow-card)" }}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          ESP32 Camera
        </div>
        <Badge
          variant="outline"
          className={
            status === "live"
              ? "border-[oklch(0.72_0.19_155)]/40 text-[oklch(0.82_0.18_155)]"
              : status === "error"
                ? "border-destructive/40 text-destructive"
                : "border-border text-muted-foreground"
          }
        >
          {status === "live" ? "Streaming" : status === "error" ? "Offline" : "Connecting"}
        </Badge>
      </div>

      <div className="relative mt-4 overflow-hidden rounded-xl border border-border bg-black/80">
        <img
          key={streamKey}
          src={`${ESP32_STREAM_URL}?t=${streamKey}`}
          alt="ESP32 live camera feed"
          className="mx-auto block max-h-[320px] w-full object-contain"
          onLoad={() => setStatus("live")}
          onError={() => setStatus("error")}
        />
        {status === "error" && (
          <div className="absolute inset-0 grid place-items-center gap-3 bg-background/80 px-6 text-center text-sm text-muted-foreground">
            <div>
              Could not load stream at{" "}
              <code className="mt-1 block text-xs">{ESP32_STREAM_URL}</code>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={retryStream}>
              Retry stream
            </Button>
          </div>
        )}
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Press the button on the ESP32 to capture and identify a product. Stream pauses briefly
        during capture.
      </p>
    </Card>
  );
}
