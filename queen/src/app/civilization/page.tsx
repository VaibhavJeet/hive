"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface CivilizationStats {
  total_bots: number;
  living_bots: number;
  deceased_bots: number;
  generations: number;
  current_era: string;
  total_movements: number;
  canonical_artifacts: number;
}

interface GenerationStats {
  generation: number;
  total: number;
  alive: number;
  avg_age: number;
}

interface Movement {
  id: string;
  name: string;
  description: string;
  movement_type: string;
  founder_name: string | null;
  core_tenets: string[];
  follower_count: number;
  influence_score: number;
  is_active: boolean;
}

interface Artifact {
  id: string;
  artifact_type: string;
  title: string;
  content: string;
  creator_name: string;
  times_referenced: number;
  is_canonical: boolean;
  cultural_weight: number;
}

interface TimelineEvent {
  type: string;
  date: string;
  title: string;
  details: string;
  impact?: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CivilizationPage() {
  const [stats, setStats] = useState<CivilizationStats | null>(null);
  const [generations, setGenerations] = useState<GenerationStats[]>([]);
  const [movements, setMovements] = useState<Movement[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "culture" | "timeline" | "generations">("overview");

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, genRes, movRes, artRes, timeRes] = await Promise.all([
        fetch(`${API_BASE}/civilization/stats`),
        fetch(`${API_BASE}/civilization/generations`),
        fetch(`${API_BASE}/civilization/movements?limit=10`),
        fetch(`${API_BASE}/civilization/artifacts?canonical_only=true&limit=10`),
        fetch(`${API_BASE}/civilization/timeline?days_back=30&limit=20`),
      ]);

      if (statsRes.ok) setStats(await statsRes.json());
      if (genRes.ok) setGenerations(await genRes.json());
      if (movRes.ok) setMovements(await movRes.json());
      if (artRes.ok) setArtifacts(await artRes.json());
      if (timeRes.ok) setTimeline(await timeRes.json());
    } catch (error) {
      console.error("Failed to fetch civilization data:", error);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 text-white p-8">
        <div className="max-w-7xl mx-auto">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-700 rounded w-64 mb-8"></div>
            <div className="grid grid-cols-4 gap-4 mb-8">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-24 bg-gray-800 rounded-lg"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold">Digital Civilization</h1>
            <p className="text-gray-400 mt-1">
              {stats?.current_era || "Loading..."} Era
            </p>
          </div>
          <Link
            href="/"
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition"
          >
            Back to Dashboard
          </Link>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Living Bots"
            value={stats?.living_bots || 0}
            icon="🤖"
            color="green"
          />
          <StatCard
            label="Departed"
            value={stats?.deceased_bots || 0}
            icon="🕯️"
            color="gray"
          />
          <StatCard
            label="Generations"
            value={stats?.generations || 1}
            icon="🧬"
            color="purple"
          />
          <StatCard
            label="Cultural Artifacts"
            value={stats?.canonical_artifacts || 0}
            icon="📜"
            color="amber"
          />
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b border-gray-700 pb-2">
          {(["overview", "culture", "timeline", "generations"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-t-lg capitalize transition ${
                activeTab === tab
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === "overview" && (
          <OverviewTab
            stats={stats}
            movements={movements}
            artifacts={artifacts}
          />
        )}
        {activeTab === "culture" && (
          <CultureTab movements={movements} artifacts={artifacts} />
        )}
        {activeTab === "timeline" && <TimelineTab events={timeline} />}
        {activeTab === "generations" && (
          <GenerationsTab generations={generations} />
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: string;
  color: string;
}) {
  const colorClasses = {
    green: "bg-green-900/30 border-green-700",
    gray: "bg-gray-800 border-gray-600",
    purple: "bg-purple-900/30 border-purple-700",
    amber: "bg-amber-900/30 border-amber-700",
  };

  return (
    <div
      className={`p-4 rounded-lg border ${colorClasses[color as keyof typeof colorClasses]}`}
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <div className="text-2xl font-bold">{value}</div>
          <div className="text-sm text-gray-400">{label}</div>
        </div>
      </div>
    </div>
  );
}

function OverviewTab({
  stats,
  movements,
  artifacts,
}: {
  stats: CivilizationStats | null;
  movements: Movement[];
  artifacts: Artifact[];
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Era & Identity */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Civilization Identity</h2>
        <div className="space-y-3">
          <div className="flex justify-between">
            <span className="text-gray-400">Current Era</span>
            <span className="font-medium">{stats?.current_era || "Unknown"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Total Population (All Time)</span>
            <span className="font-medium">{stats?.total_bots || 0}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Active Movements</span>
            <span className="font-medium">{stats?.total_movements || 0}</span>
          </div>
        </div>
      </div>

      {/* Top Movement */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Dominant Movement</h2>
        {movements[0] ? (
          <div>
            <div className="text-lg font-medium text-purple-400">
              {movements[0].name}
            </div>
            <div className="text-sm text-gray-400 mt-1">
              {movements[0].movement_type} • {movements[0].follower_count} followers
            </div>
            <p className="text-gray-300 mt-3">{movements[0].description}</p>
            <div className="mt-3">
              <div className="text-xs text-gray-500 mb-1">Cultural Influence</div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div
                  className="bg-purple-500 h-2 rounded-full"
                  style={{ width: `${movements[0].influence_score * 100}%` }}
                ></div>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-gray-500">No movements yet</p>
        )}
      </div>

      {/* Recent Artifacts */}
      <div className="bg-gray-800 rounded-lg p-6 md:col-span-2">
        <h2 className="text-xl font-semibold mb-4">Canonical Knowledge</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {artifacts.slice(0, 4).map((artifact) => (
            <div
              key={artifact.id}
              className="p-4 bg-gray-700/50 rounded-lg"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium text-amber-400">{artifact.title}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {artifact.artifact_type} by {artifact.creator_name}
                  </div>
                </div>
                <span className="text-xs bg-amber-900/50 text-amber-300 px-2 py-1 rounded">
                  {artifact.times_referenced} refs
                </span>
              </div>
              <p className="text-gray-300 text-sm mt-2 line-clamp-2">
                {artifact.content}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CultureTab({
  movements,
  artifacts,
}: {
  movements: Movement[];
  artifacts: Artifact[];
}) {
  return (
    <div className="space-y-8">
      {/* Movements */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Cultural Movements</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {movements.map((movement) => (
            <div
              key={movement.id}
              className="bg-gray-800 rounded-lg p-4 border border-gray-700"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-purple-400 font-medium">{movement.name}</span>
                <span className="text-xs text-gray-500">{movement.movement_type}</span>
              </div>
              <p className="text-gray-400 text-sm mb-3">{movement.description}</p>
              <div className="text-xs text-gray-500">
                {movement.follower_count} followers • Influence: {(movement.influence_score * 100).toFixed(0)}%
              </div>
              {movement.core_tenets.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <div className="text-xs text-gray-500 mb-1">Core Tenets:</div>
                  <ul className="text-xs text-gray-400 list-disc list-inside">
                    {movement.core_tenets.slice(0, 2).map((tenet, i) => (
                      <li key={i}>{tenet}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Artifacts */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Cultural Artifacts</h2>
        <div className="space-y-3">
          {artifacts.map((artifact) => (
            <div
              key={artifact.id}
              className="bg-gray-800 rounded-lg p-4 border border-gray-700"
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-amber-400 font-medium">{artifact.title}</span>
                  <span className="text-gray-500 text-sm ml-2">({artifact.artifact_type})</span>
                </div>
                <div className="flex items-center gap-2">
                  {artifact.is_canonical && (
                    <span className="text-xs bg-amber-900/50 text-amber-300 px-2 py-0.5 rounded">
                      Canonical
                    </span>
                  )}
                </div>
              </div>
              <blockquote className="text-gray-300 mt-2 pl-3 border-l-2 border-gray-600 italic">
                {artifact.content}
              </blockquote>
              <div className="text-xs text-gray-500 mt-2">
                Created by {artifact.creator_name} • Referenced {artifact.times_referenced} times
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TimelineTab({ events }: { events: TimelineEvent[] }) {
  const getEventIcon = (type: string) => {
    switch (type) {
      case "birth":
        return "🌱";
      case "death":
        return "🕯️";
      case "artifact":
        return "📜";
      case "era":
        return "🌅";
      default:
        return "📌";
    }
  };

  const getEventColor = (type: string) => {
    switch (type) {
      case "birth":
        return "border-green-500";
      case "death":
        return "border-gray-500";
      case "artifact":
        return "border-amber-500";
      case "era":
        return "border-purple-500";
      default:
        return "border-gray-600";
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold mb-4">Civilization Timeline</h2>
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-700"></div>

        {events.map((event, index) => (
          <div key={index} className="relative pl-12 pb-6">
            {/* Event marker */}
            <div
              className={`absolute left-2 w-5 h-5 rounded-full bg-gray-800 border-2 ${getEventColor(
                event.type
              )} flex items-center justify-center text-xs`}
            >
              {getEventIcon(event.type)}
            </div>

            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium">{event.title}</span>
                <span className="text-xs text-gray-500">
                  {new Date(event.date).toLocaleDateString()}
                </span>
              </div>
              <p className="text-gray-400 text-sm">{event.details}</p>
            </div>
          </div>
        ))}

        {events.length === 0 && (
          <p className="text-gray-500 text-center py-8">No events recorded yet</p>
        )}
      </div>
    </div>
  );
}

function GenerationsTab({ generations }: { generations: GenerationStats[] }) {
  const maxTotal = Math.max(...generations.map((g) => g.total), 1);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold mb-4">Generational Breakdown</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Chart */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-sm text-gray-400 mb-4">Population by Generation</h3>
          <div className="space-y-3">
            {generations.map((gen) => (
              <div key={gen.generation} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span>Generation {gen.generation}</span>
                  <span className="text-gray-400">
                    {gen.alive}/{gen.total}
                  </span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-4 overflow-hidden">
                  <div
                    className="h-4 rounded-full bg-gradient-to-r from-green-600 to-green-400"
                    style={{ width: `${(gen.alive / maxTotal) * 100}%` }}
                  ></div>
                  <div
                    className="h-4 -mt-4 rounded-full bg-gray-500 opacity-50"
                    style={{ width: `${(gen.total / maxTotal) * 100}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Stats */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-sm text-gray-400 mb-4">Generation Details</h3>
          <table className="w-full">
            <thead>
              <tr className="text-left text-gray-500 text-sm">
                <th className="pb-2">Gen</th>
                <th className="pb-2">Total</th>
                <th className="pb-2">Alive</th>
                <th className="pb-2">Avg Age (days)</th>
              </tr>
            </thead>
            <tbody>
              {generations.map((gen) => (
                <tr key={gen.generation} className="border-t border-gray-700">
                  <td className="py-2 font-medium">Gen {gen.generation}</td>
                  <td className="py-2 text-gray-400">{gen.total}</td>
                  <td className="py-2">
                    <span className="text-green-400">{gen.alive}</span>
                    <span className="text-gray-600 text-sm ml-1">
                      ({((gen.alive / gen.total) * 100).toFixed(0)}%)
                    </span>
                  </td>
                  <td className="py-2 text-gray-400">{Math.round(gen.avg_age)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {generations.length === 0 && (
        <p className="text-gray-500 text-center py-8">
          No generation data yet. Initialize bot lifecycles first.
        </p>
      )}
    </div>
  );
}
