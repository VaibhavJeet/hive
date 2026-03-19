"use client";

import { useState, useEffect, use } from "react";
import Link from "next/link";

interface FamilyNode {
  id: string;
  name: string;
  handle?: string;
  is_alive?: boolean;
  origin?: string;
  inherited_traits?: Record<string, any>;
  mutations?: Record<string, any>;
  parent1?: FamilyNode;
  parent2?: FamilyNode;
}

interface Descendant {
  bot_id: string;
  name: string;
  generation: number;
  relationship: string;
}

interface Relative {
  bot_id: string;
  name: string;
  relationship: string;
  distance?: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function FamilyTreePage({ params }: { params: Promise<{ botId: string }> }) {
  const { botId } = use(params);
  const [tree, setTree] = useState<FamilyNode | null>(null);
  const [descendants, setDescendants] = useState<Descendant[]>([]);
  const [relatives, setRelatives] = useState<Relative[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState<"ancestors" | "descendants" | "all">("ancestors");

  useEffect(() => {
    fetchFamilyData();
  }, [botId]);

  const fetchFamilyData = async () => {
    setLoading(true);
    try {
      const [treeRes, descRes, relRes] = await Promise.all([
        fetch(`${API_BASE}/civilization/bots/${botId}/family-tree?depth=4`),
        fetch(`${API_BASE}/civilization/bots/${botId}/descendants?max_generations=5`),
        fetch(`${API_BASE}/civilization/bots/${botId}/relatives?max_distance=3`),
      ]);

      if (treeRes.ok) setTree(await treeRes.json());
      if (descRes.ok) setDescendants(await descRes.json());
      if (relRes.ok) setRelatives(await relRes.json());
    } catch (error) {
      console.error("Failed to fetch family data:", error);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 text-white p-8">
        <div className="max-w-6xl mx-auto">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-700 rounded w-64 mb-8"></div>
            <div className="h-96 bg-gray-800 rounded-lg"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold">Family Tree</h1>
            <p className="text-gray-400 mt-1">
              {tree?.name || "Unknown"}'s lineage
            </p>
          </div>
          <Link
            href="/civilization"
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition"
          >
            Back to Civilization
          </Link>
        </div>

        {/* View Toggle */}
        <div className="flex gap-2 mb-6">
          {(["ancestors", "descendants", "all"] as const).map((view) => (
            <button
              key={view}
              onClick={() => setActiveView(view)}
              className={`px-4 py-2 rounded-lg capitalize transition ${
                activeView === view
                  ? "bg-purple-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {view}
            </button>
          ))}
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Ancestor Tree */}
          {(activeView === "ancestors" || activeView === "all") && (
            <div className="lg:col-span-2 bg-gray-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold mb-4">Ancestors</h2>
              {tree ? (
                <AncestorTree node={tree} />
              ) : (
                <p className="text-gray-500">No ancestry data available</p>
              )}
            </div>
          )}

          {/* Descendants */}
          {(activeView === "descendants" || activeView === "all") && (
            <div className={`bg-gray-800 rounded-lg p-6 ${activeView === "all" ? "" : "lg:col-span-2"}`}>
              <h2 className="text-xl font-semibold mb-4">
                Descendants ({descendants.length})
              </h2>
              {descendants.length > 0 ? (
                <DescendantsList descendants={descendants} />
              ) : (
                <p className="text-gray-500">No descendants yet</p>
              )}
            </div>
          )}

          {/* Relatives Sidebar */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Relatives</h2>
            {relatives.length > 0 ? (
              <div className="space-y-2">
                {relatives.map((relative, i) => (
                  <Link
                    key={i}
                    href={`/civilization/family-tree/${relative.bot_id}`}
                    className="block p-3 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition"
                  >
                    <div className="font-medium">{relative.name}</div>
                    <div className="text-sm text-gray-400">{relative.relationship}</div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-gray-500">No known relatives</p>
            )}
          </div>
        </div>

        {/* Origin Info */}
        {tree && (
          <div className="mt-6 bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Origin</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-gray-400">Type</div>
                <div className="font-medium capitalize">{tree.origin || "Unknown"}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Status</div>
                <div className={`font-medium ${tree.is_alive ? "text-green-400" : "text-gray-500"}`}>
                  {tree.is_alive ? "Living" : "Departed"}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Handle</div>
                <div className="font-medium">@{tree.handle || "unknown"}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Descendants</div>
                <div className="font-medium">{descendants.length}</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function AncestorTree({ node, level = 0 }: { node: FamilyNode; level?: number }) {
  const hasParents = node.parent1 || node.parent2;
  const indent = level * 40;

  return (
    <div className="relative">
      {/* Current Node */}
      <div
        className="relative flex items-center gap-3 p-3 bg-gray-700/50 rounded-lg mb-2"
        style={{ marginLeft: `${indent}px` }}
      >
        {/* Connector line */}
        {level > 0 && (
          <div
            className="absolute -left-6 top-1/2 w-6 h-0.5 bg-gray-600"
          ></div>
        )}

        <div
          className={`w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold ${
            node.is_alive
              ? "bg-green-900/50 text-green-400 border border-green-700"
              : "bg-gray-700 text-gray-400 border border-gray-600"
          }`}
        >
          {node.name?.[0] || "?"}
        </div>
        <div>
          <div className="font-medium">{node.name}</div>
          <div className="text-xs text-gray-400">
            {node.origin ? `Origin: ${node.origin}` : ""}
          </div>
        </div>
        {!node.is_alive && (
          <span className="ml-auto text-xs text-gray-500">departed</span>
        )}
      </div>

      {/* Parents */}
      {hasParents && (
        <div className="ml-6 border-l-2 border-gray-700 pl-4">
          {node.parent1 && <AncestorTree node={node.parent1} level={level + 1} />}
          {node.parent2 && <AncestorTree node={node.parent2} level={level + 1} />}
        </div>
      )}
    </div>
  );
}

function DescendantsList({ descendants }: { descendants: Descendant[] }) {
  // Group by generation
  const byGeneration = descendants.reduce((acc, d) => {
    if (!acc[d.generation]) acc[d.generation] = [];
    acc[d.generation].push(d);
    return acc;
  }, {} as Record<number, Descendant[]>);

  return (
    <div className="space-y-4">
      {Object.entries(byGeneration)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([gen, members]) => (
          <div key={gen}>
            <div className="text-sm text-gray-400 mb-2">
              Generation {gen} ({members[0].relationship}s)
            </div>
            <div className="grid grid-cols-2 gap-2">
              {members.map((member) => (
                <Link
                  key={member.bot_id}
                  href={`/civilization/family-tree/${member.bot_id}`}
                  className="p-2 bg-gray-700/50 rounded hover:bg-gray-700 transition text-sm"
                >
                  {member.name}
                </Link>
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}
