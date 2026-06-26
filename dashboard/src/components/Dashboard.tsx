import { useEffect, useState } from "react";
import CameraFeed from "@/components/CameraFeed";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { API_BASE } from "@/lib/config";

type StorePrice = { store: string; price: number | string };

type HistoryItem = {
  name?: string;
  product?: string;
  timestamp?: string | number;
  scanned_at?: string;
  kroger_price?: number | string;
  local_price?: number | string;
  kroger?: number | string;
  local?: number | string;
  prices?: { kroger?: number; local?: number } | StorePrice[];
};

const ICONS: Record<string, string> = {
  gatorade: "🥤",
  lotion: "🧴",
  "peanut butter": "🥜",
};

function iconFor(name: string) {
  if (!name) return "🛒";
  const k = name.toLowerCase();
  for (const key of Object.keys(ICONS)) {
    if (k.includes(key)) return ICONS[key];
  }
  return "🛒";
}

function asNumber(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : parseFloat(String(v).replace(/[^0-9.]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function priceFromStore(prices: StorePrice[] | undefined, storeNeedle: string) {
  if (!prices) return null;
  const row = prices.find((p) => p.store.toLowerCase().includes(storeNeedle));
  return row ? asNumber(row.price) : null;
}

function normalize(item: HistoryItem) {
  const priceList = Array.isArray(item.prices) ? item.prices : undefined;
  const flatPrices = !Array.isArray(item.prices) ? item.prices : undefined;
  const kroger =
    asNumber(item.kroger_price ?? item.kroger ?? flatPrices?.kroger) ??
    priceFromStore(priceList, "kroger");
  const local =
    asNumber(item.local_price ?? item.local ?? flatPrices?.local) ??
    priceFromStore(priceList, "local");
  return {
    name: item.name ?? item.product ?? "Unknown",
    timestamp: item.timestamp ?? item.scanned_at,
    kroger,
    local,
  };
}

function formatTime(ts?: string | number) {
  if (!ts) return "—";
  const d = new Date(typeof ts === "number" && ts < 1e12 ? ts * 1000 : ts);
  if (isNaN(d.getTime())) return String(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function Dashboard() {
  const [history, setHistory] = useState<ReturnType<typeof normalize>[]>([]);
  const [status, setStatus] = useState<"connecting" | "live" | "error">("connecting");
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const res = await fetch(`${API_BASE}/history`, { cache: "no-store" });
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        const list: HistoryItem[] = Array.isArray(data) ? data : data.history ?? data.items ?? [];
        if (!cancelled) {
          setHistory(list.map(normalize));
          setStatus("live");
          setLastUpdate(new Date());
        }
      } catch {
        if (!cancelled) setStatus("error");
      }
    }
    poll();
    const id = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const latest = history[0];
  const recent = history.slice(0, 5);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-10 flex items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-3">
              <div
                className="grid h-11 w-11 place-items-center rounded-xl text-xl font-bold text-primary-foreground"
                style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-glow)" }}
              >
                G
              </div>
              <h1 className="text-3xl font-semibold tracking-tight">GrocerAI</h1>
            </div>
            <p className="mt-2 text-muted-foreground">Smart Grocery Price Optimization</p>
          </div>
          <StatusPill status={status} lastUpdate={lastUpdate} />
        </header>

        <section className="grid gap-6 lg:grid-cols-5">
          <LastScannedCard item={latest} />
          <PriceComparisonCard item={latest} />
        </section>

        <section className="mt-6">
          <CameraFeed />
        </section>

        <section className="mt-6">
          <HistoryFeed items={recent} />
        </section>

        <footer className="mt-10 text-center text-xs text-muted-foreground">
          Polling {API_BASE}/history every 3s
        </footer>
      </div>
    </div>
  );
}

function StatusPill({ status, lastUpdate }: { status: "connecting" | "live" | "error"; lastUpdate: Date | null }) {
  const color =
    status === "live"
      ? "bg-[oklch(0.72_0.19_155)]"
      : status === "error"
        ? "bg-destructive"
        : "bg-muted-foreground";
  const label = status === "live" ? "Live" : status === "error" ? "Disconnected" : "Connecting";
  return (
    <div className="flex items-center gap-3 rounded-full border border-border bg-card px-4 py-2 text-sm">
      <span className="relative flex h-2.5 w-2.5">
        {status === "live" && (
          <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${color}`} />
        )}
        <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${color}`} />
      </span>
      <span className="font-medium">{label}</span>
      {lastUpdate && (
        <span className="text-muted-foreground">· {lastUpdate.toLocaleTimeString()}</span>
      )}
    </div>
  );
}

function LastScannedCard({ item }: { item?: ReturnType<typeof normalize> }) {
  return (
    <Card
      className="lg:col-span-2 border-border p-6"
      style={{ background: "var(--gradient-card)", boxShadow: "var(--shadow-card)" }}
    >
      <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        Last Scanned Item
      </div>
      {item ? (
        <div className="mt-6 flex items-center gap-5">
          <div className="grid h-20 w-20 place-items-center rounded-2xl border border-border bg-secondary text-5xl">
            {iconFor(item.name)}
          </div>
          <div className="min-w-0">
            <div className="truncate text-2xl font-semibold capitalize">{item.name}</div>
            <div className="mt-1 text-sm text-muted-foreground">
              Scanned at {formatTime(item.timestamp)}
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-6 text-muted-foreground">Waiting for first scan…</div>
      )}
    </Card>
  );
}

function PriceComparisonCard({ item }: { item?: ReturnType<typeof normalize> }) {
  const kroger = item?.kroger ?? null;
  const local = item?.local ?? null;
  const both = kroger !== null && local !== null;
  const krogerWins = both && (kroger as number) < (local as number);
  const localWins = both && (local as number) < (kroger as number);

  return (
    <Card
      className="lg:col-span-3 border-border p-6"
      style={{ background: "var(--gradient-card)", boxShadow: "var(--shadow-card)" }}
    >
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Price Comparison
        </div>
        {both && (
          <Badge className="border-0 bg-[oklch(0.72_0.19_155)]/15 text-[oklch(0.82_0.18_155)]">
            Save ${Math.abs((kroger as number) - (local as number)).toFixed(2)}
          </Badge>
        )}
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-border">
        <table className="w-full text-left">
          <thead className="bg-secondary/60 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium">Store</th>
              <th className="px-4 py-3 text-right font-medium">Price</th>
              <th className="px-4 py-3 text-right font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            <PriceRow store="Kroger" price={kroger} winner={krogerWins} />
            <PriceRow store="Local Market" price={local} winner={localWins} />
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function PriceRow({ store, price, winner }: { store: string; price: number | null; winner: boolean }) {
  return (
    <tr className={winner ? "bg-[oklch(0.72_0.19_155)]/10" : ""}>
      <td className="px-4 py-4 font-medium">{store}</td>
      <td
        className={`px-4 py-4 text-right font-mono text-lg ${
          winner ? "text-[oklch(0.82_0.18_155)] font-semibold" : ""
        }`}
      >
        {price === null ? "—" : `$${price.toFixed(2)}`}
      </td>
      <td className="px-4 py-4 text-right">
        {winner ? (
          <span className="rounded-full bg-[oklch(0.72_0.19_155)]/20 px-3 py-1 text-xs font-semibold text-[oklch(0.82_0.18_155)]">
            ✓ Cheaper
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>
    </tr>
  );
}

function HistoryFeed({ items }: { items: ReturnType<typeof normalize>[] }) {
  return (
    <Card
      className="border-border p-6"
      style={{ background: "var(--gradient-card)", boxShadow: "var(--shadow-card)" }}
    >
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Scan History
        </div>
        <span className="text-xs text-muted-foreground">Last 5 items</span>
      </div>

      {items.length === 0 ? (
        <div className="mt-6 text-muted-foreground">No scans yet.</div>
      ) : (
        <ul className="mt-4 divide-y divide-border">
          {items.map((it, i) => {
            const k = it.kroger;
            const l = it.local;
            const best =
              k !== null && l !== null ? Math.min(k as number, l as number) : (k ?? l);
            return (
              <li key={i} className="flex items-center gap-4 py-3">
                <div className="grid h-11 w-11 place-items-center rounded-xl border border-border bg-secondary text-2xl">
                  {iconFor(it.name)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium capitalize">{it.name}</div>
                  <div className="text-xs text-muted-foreground">{formatTime(it.timestamp)}</div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-sm text-[oklch(0.82_0.18_155)]">
                    {best !== null && best !== undefined ? `$${(best as number).toFixed(2)}` : "—"}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Best</div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}