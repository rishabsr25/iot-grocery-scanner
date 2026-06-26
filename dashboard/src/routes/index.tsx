import { createFileRoute } from "@tanstack/react-router";
import Dashboard from "@/components/Dashboard";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "GrocerAI — Smart Grocery Price Optimization" },
      { name: "description", content: "Live dashboard comparing Kroger vs Local Market grocery prices with AI-powered scanning." },
      { property: "og:title", content: "GrocerAI — Smart Grocery Price Optimization" },
      { property: "og:description", content: "Live dashboard comparing Kroger vs Local Market grocery prices with AI-powered scanning." },
    ],
  }),
  component: Index,
});

function Index() {
  return <Dashboard />;
}
