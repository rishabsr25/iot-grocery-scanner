/** Flask identify/history API (same host as IDENTIFY_URL in firmware secrets.h). */
export const API_BASE =
  import.meta.env.VITE_API_BASE?.replace(/\/$/, "") ?? "http://192.168.1.30:5000";

/** ESP32 MJPEG stream (http://<esp32-ip>:81/stream). Set VITE_ESP32_STREAM_URL in .env.local. */
export const ESP32_STREAM_URL =
  import.meta.env.VITE_ESP32_STREAM_URL ?? "http://192.168.1.31:81/stream";
