"use client";

import { useState, useEffect, use, useRef } from "react";
import Link from "next/link";
import * as d3 from "d3";

interface FamilyNode {
  id: string;
  name: string;
  handle?: string;
  is_alive?: boolean;
  origin?: string;
  inherited_traits?: Record<string, unknown>;
  mutations?: Record<string, unknown>;
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

// D3 hierarchy node type
interface TreeNode {
  id: string;
  name: string;
  is_alive?: boolean;
  origin?: string;
  children?: TreeNode[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Colors
const COLORS = {
  alive: "#44ff88",
  departed: "#666666",
  link: "#2a2a2a",
  linkHover: "#ff00aa",
  background: "#141414",
  cardBg: "#0a0a0a",
  border: "#2a2a2a",
  text: "#ffffff",
  textMuted: "#888888",
  accent: "#ff00aa",
};

export default function FamilyTreePage({ params }: { params: Promise<{ botId: string }> }) {
  const { botId } = use(params);
  const [tree, setTree] = useState<FamilyNode | null>(null);
  const [descendants, setDescendants] = useState<Descendant[]>([]);
  const [relatives, setRelatives] = useState<Relative[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState<"ancestors" | "descendants" | "all">("ancestors");

  useEffect(() => {
    let cancelled = false;

    const fetchFamilyData = async () => {
      setLoading(true);
      try {
        const [treeRes, descRes, relRes] = await Promise.all([
          fetch(`${API_BASE}/civilization/bots/${botId}/family-tree?depth=4`),
          fetch(`${API_BASE}/civilization/bots/${botId}/descendants?max_generations=5`),
          fetch(`${API_BASE}/civilization/bots/${botId}/relatives?max_distance=3`),
        ]);

        if (cancelled) return;

        if (treeRes.ok) setTree(await treeRes.json());
        if (descRes.ok) setDescendants(await descRes.json());
        if (relRes.ok) setRelatives(await relRes.json());
      } catch (error) {
        if (!cancelled) {
          console.error("Failed to fetch family data:", error);
        }
      }
      if (!cancelled) {
        setLoading(false);
      }
    };

    fetchFamilyData();

    return () => {
      cancelled = true;
    };
  }, [botId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background text-white p-8">
        <div className="max-w-6xl mx-auto">
          <div className="animate-pulse">
            <div className="h-8 bg-[#2a2a2a] rounded w-64 mb-8"></div>
            <div className="h-96 bg-[#141414] rounded-lg"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-white p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold">Family Tree</h1>
            <p className="text-[#666666] mt-1">
              {tree?.name || "Unknown"}&apos;s lineage
            </p>
          </div>
          <Link
            href="/civilization"
            className="px-4 py-2 bg-[#141414] border border-[#2a2a2a] hover:border-[#3a3a3a] rounded-lg transition"
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
                  ? "bg-[#ff00aa]/20 text-[#ff00aa] border border-[#ff00aa]/30"
                  : "bg-[#141414] text-[#666666] border border-[#2a2a2a] hover:text-white"
              }`}
            >
              {view}
            </button>
          ))}
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Ancestor Tree - D3 Visualization */}
          {(activeView === "ancestors" || activeView === "all") && (
            <div className="lg:col-span-2 bg-[#141414] rounded-lg p-6 border border-[#2a2a2a]">
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <span className="text-[#ff00aa]">&#x25B2;</span> Ancestors
              </h2>
              {tree ? (
                <AncestorTreeD3 node={tree} currentBotId={botId} />
              ) : (
                <p className="text-[#555555]">No ancestry data available</p>
              )}
            </div>
          )}

          {/* Descendants - D3 Visualization */}
          {(activeView === "descendants" || activeView === "all") && (
            <div className={`bg-[#141414] rounded-lg p-6 border border-[#2a2a2a] ${activeView === "all" ? "" : "lg:col-span-2"}`}>
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <span className="text-[#44ff88]">&#x25BC;</span> Descendants ({descendants.length})
              </h2>
              {descendants.length > 0 ? (
                <DescendantsTreeD3 descendants={descendants} rootName={tree?.name || "Unknown"} rootId={botId} />
              ) : (
                <p className="text-[#555555]">No descendants yet</p>
              )}
            </div>
          )}

          {/* Relatives Sidebar */}
          <div className="bg-[#141414] rounded-lg p-6 border border-[#2a2a2a]">
            <h2 className="text-xl font-semibold mb-4">Relatives</h2>
            {relatives.length > 0 ? (
              <div className="space-y-2 max-h-100 overflow-y-auto">
                {relatives.map((relative, i) => (
                  <Link
                    key={i}
                    href={`/civilization/family-tree/${relative.bot_id}`}
                    className="block p-3 bg-background rounded-lg border border-[#1a1a1a] hover:border-[#ff00aa]/50 hover:bg-[#ff00aa]/5 transition group"
                  >
                    <div className="font-medium group-hover:text-[#ff00aa] transition">{relative.name}</div>
                    <div className="text-sm text-[#666666]">{relative.relationship}</div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-[#555555]">No known relatives</p>
            )}
          </div>
        </div>

        {/* Origin Info */}
        {tree && (
          <div className="mt-6 bg-[#141414] rounded-lg p-6 border border-[#2a2a2a]">
            <h2 className="text-xl font-semibold mb-4">Origin</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-[#666666]">Type</div>
                <div className="font-medium capitalize">{tree.origin || "Unknown"}</div>
              </div>
              <div>
                <div className="text-sm text-[#666666]">Status</div>
                <div className={`font-medium ${tree.is_alive ? "text-[#44ff88]" : "text-[#555555]"}`}>
                  {tree.is_alive ? "Living" : "Departed"}
                </div>
              </div>
              <div>
                <div className="text-sm text-[#666666]">Handle</div>
                <div className="font-medium">@{tree.handle || "unknown"}</div>
              </div>
              <div>
                <div className="text-sm text-[#666666]">Descendants</div>
                <div className="font-medium">{descendants.length}</div>
              </div>
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="mt-6 bg-[#141414] rounded-lg p-4 border border-[#2a2a2a]">
          <div className="flex flex-wrap gap-6 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-[#44ff88] border-2 border-[#44ff88]/50"></div>
              <span className="text-[#888888]">Living</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-[#333333] border-2 border-[#555555]"></div>
              <span className="text-[#888888]">Departed</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-[#ff00aa] border-2 border-[#ff00aa]/50"></div>
              <span className="text-[#888888]">Current Bot</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-0.5 bg-[#2a2a2a]"></div>
              <span className="text-[#888888]">Lineage Connection</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Convert FamilyNode to hierarchical structure for D3
function buildAncestorHierarchy(n: FamilyNode): TreeNode {
  const children: TreeNode[] = [];
  if (n.parent1) children.push(buildAncestorHierarchy(n.parent1));
  if (n.parent2) children.push(buildAncestorHierarchy(n.parent2));

  return {
    id: n.id,
    name: n.name,
    is_alive: n.is_alive,
    origin: n.origin,
    children: children.length > 0 ? children : undefined,
  };
}

// D3-powered Ancestor Tree (bottom-up visualization)
function AncestorTreeD3({ node, currentBotId }: { node: FamilyNode; currentBotId: string }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const hierarchyData = buildAncestorHierarchy(node);
    const container = containerRef.current;
    const width = container.clientWidth;

    // Calculate depth for height
    const getDepth = (n: TreeNode): number => {
      if (!n.children || n.children.length === 0) return 1;
      return 1 + Math.max(...n.children.map(getDepth));
    };
    const depth = getDepth(hierarchyData);
    const height = Math.max(300, depth * 100);

    // Clear previous content
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current)
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", `0 0 ${width} ${height}`);

    // Create hierarchy and tree layout (bottom-up)
    const root = d3.hierarchy(hierarchyData);
    const treeLayout = d3.tree<TreeNode>()
      .size([width - 100, height - 80])
      .separation((a, b) => (a.parent === b.parent ? 1.5 : 2));

    treeLayout(root);

    // Flip Y coordinates for bottom-up tree (root at bottom)
    root.each((d) => {
      d.y = height - 50 - (d.y ?? 0);
    });

    const g = svg.append("g").attr("transform", "translate(50, 10)");

    // Draw links with curved paths
    g.selectAll(".link")
      .data(root.links())
      .enter()
      .append("path")
      .attr("class", "link")
      .attr("fill", "none")
      .attr("stroke", COLORS.link)
      .attr("stroke-width", 2)
      .attr("d", d => {
        const sourceX = d.source.x ?? 0;
        const sourceY = d.source.y ?? 0;
        const targetX = d.target.x ?? 0;
        const targetY = d.target.y ?? 0;
        // Create a smooth curve between source and target
        const midY = (sourceY + targetY) / 2;
        return `M${sourceX},${sourceY} C${sourceX},${midY} ${targetX},${midY} ${targetX},${targetY}`;
      });

    // Draw nodes
    const nodes = g.selectAll(".node")
      .data(root.descendants())
      .enter()
      .append("g")
      .attr("class", "node")
      .attr("transform", d => `translate(${d.x},${d.y})`)
      .style("cursor", "pointer");

    // Node circles
    nodes.append("circle")
      .attr("r", d => d.data.id === currentBotId ? 22 : 18)
      .attr("fill", d => {
        if (d.data.id === currentBotId) return COLORS.accent;
        return d.data.is_alive ? COLORS.alive : "#333333";
      })
      .attr("stroke", d => {
        if (d.data.id === currentBotId) return COLORS.accent;
        return d.data.is_alive ? `${COLORS.alive}80` : "#555555";
      })
      .attr("stroke-width", 3)
      .attr("opacity", d => d.data.id === currentBotId ? 1 : 0.9);

    // Glow effect for current bot
    nodes.filter(d => d.data.id === currentBotId)
      .insert("circle", ":first-child")
      .attr("r", 30)
      .attr("fill", "none")
      .attr("stroke", COLORS.accent)
      .attr("stroke-width", 2)
      .attr("opacity", 0.3);

    // Node initials
    nodes.append("text")
      .attr("dy", 5)
      .attr("text-anchor", "middle")
      .attr("fill", d => d.data.id === currentBotId ? "#ffffff" : (d.data.is_alive ? "#000000" : "#cccccc"))
      .attr("font-size", "14px")
      .attr("font-weight", "bold")
      .text(d => d.data.name?.[0]?.toUpperCase() || "?");

    // Node labels
    nodes.append("text")
      .attr("dy", d => d.depth === 0 ? 40 : -28)
      .attr("text-anchor", "middle")
      .attr("fill", COLORS.text)
      .attr("font-size", "12px")
      .attr("font-weight", d => d.data.id === currentBotId ? "bold" : "normal")
      .text(d => d.data.name || "Unknown");

    // Origin labels for non-root nodes
    nodes.filter(d => d.depth > 0 && Boolean(d.data.origin))
      .append("text")
      .attr("dy", -42)
      .attr("text-anchor", "middle")
      .attr("fill", COLORS.textMuted)
      .attr("font-size", "10px")
      .text(d => d.data.origin || "");

    // Click handler for navigation
    nodes.on("click", (event, d) => {
      if (d.data.id !== currentBotId) {
        window.location.href = `/civilization/family-tree/${d.data.id}`;
      }
    });

  }, [node, currentBotId]);

  return (
    <div ref={containerRef} className="w-full overflow-x-auto">
      <svg ref={svgRef} className="w-full" style={{ minHeight: "300px" }}></svg>
    </div>
  );
}

// D3-powered Descendants Tree (top-down visualization)
function DescendantsTreeD3({
  descendants,
  rootName,
  rootId
}: {
  descendants: Descendant[];
  rootName: string;
  rootId: string;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || descendants.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;

    // Group descendants by generation
    const byGeneration = descendants.reduce((acc, d) => {
      if (!acc[d.generation]) acc[d.generation] = [];
      acc[d.generation].push(d);
      return acc;
    }, {} as Record<number, Descendant[]>);

    const generations = Object.keys(byGeneration).map(Number).sort((a, b) => a - b);
    const maxPerGen = Math.max(...generations.map(g => byGeneration[g].length));

    const nodeSpacingX = Math.min(120, (width - 100) / Math.max(maxPerGen, 1));
    const nodeSpacingY = 90;
    const height = Math.max(250, (generations.length + 1) * nodeSpacingY + 60);

    // Clear previous content
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current)
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", `0 0 ${width} ${height}`);

    const g = svg.append("g").attr("transform", "translate(0, 30)");

    // Draw root node (current bot)
    const rootX = width / 2;
    const rootY = 20;

    // Root glow
    g.append("circle")
      .attr("cx", rootX)
      .attr("cy", rootY)
      .attr("r", 28)
      .attr("fill", "none")
      .attr("stroke", COLORS.accent)
      .attr("stroke-width", 2)
      .attr("opacity", 0.3);

    g.append("circle")
      .attr("cx", rootX)
      .attr("cy", rootY)
      .attr("r", 20)
      .attr("fill", COLORS.accent)
      .attr("stroke", COLORS.accent)
      .attr("stroke-width", 3);

    g.append("text")
      .attr("x", rootX)
      .attr("y", rootY + 5)
      .attr("text-anchor", "middle")
      .attr("fill", "#ffffff")
      .attr("font-size", "14px")
      .attr("font-weight", "bold")
      .text(rootName[0]?.toUpperCase() || "?");

    g.append("text")
      .attr("x", rootX)
      .attr("y", rootY + 38)
      .attr("text-anchor", "middle")
      .attr("fill", COLORS.text)
      .attr("font-size", "12px")
      .attr("font-weight", "bold")
      .text(rootName);

    // Draw generation levels
    generations.forEach((gen, genIndex) => {
      const members = byGeneration[gen];
      const y = (genIndex + 1) * nodeSpacingY + 40;
      const totalWidth = (members.length - 1) * nodeSpacingX;
      const startX = (width - totalWidth) / 2;

      // Generation label
      g.append("text")
        .attr("x", 20)
        .attr("y", y)
        .attr("fill", COLORS.textMuted)
        .attr("font-size", "10px")
        .text(`Gen ${gen}`);

      // Draw connecting line from root/previous gen
      if (genIndex === 0) {
        // Lines from root to first generation
        const lineStartY = rootY + 25;

        // Vertical line from root
        g.append("line")
          .attr("x1", rootX)
          .attr("y1", lineStartY)
          .attr("x2", rootX)
          .attr("y2", y - 30)
          .attr("stroke", COLORS.link)
          .attr("stroke-width", 2);

        if (members.length > 1) {
          // Horizontal connector
          g.append("line")
            .attr("x1", startX)
            .attr("y1", y - 30)
            .attr("x2", startX + totalWidth)
            .attr("y2", y - 30)
            .attr("stroke", COLORS.link)
            .attr("stroke-width", 2);
        }
      }

      // Draw nodes for this generation
      members.forEach((member, i) => {
        const x = startX + i * nodeSpacingX;

        // Vertical connector to node
        g.append("line")
          .attr("x1", x)
          .attr("y1", y - 30)
          .attr("x2", x)
          .attr("y2", y - 16)
          .attr("stroke", COLORS.link)
          .attr("stroke-width", 2);

        // Node group
        const nodeGroup = g.append("g")
          .attr("transform", `translate(${x},${y})`)
          .style("cursor", "pointer")
          .on("click", () => {
            window.location.href = `/civilization/family-tree/${member.bot_id}`;
          });

        // Node circle
        nodeGroup.append("circle")
          .attr("r", 16)
          .attr("fill", COLORS.alive)
          .attr("stroke", `${COLORS.alive}80`)
          .attr("stroke-width", 2)
          .attr("opacity", 0.9);

        // Node initial
        nodeGroup.append("text")
          .attr("dy", 5)
          .attr("text-anchor", "middle")
          .attr("fill", "#000000")
          .attr("font-size", "12px")
          .attr("font-weight", "bold")
          .text(member.name[0]?.toUpperCase() || "?");

        // Node name
        nodeGroup.append("text")
          .attr("dy", 32)
          .attr("text-anchor", "middle")
          .attr("fill", COLORS.text)
          .attr("font-size", "11px")
          .text(member.name.length > 12 ? member.name.slice(0, 10) + "..." : member.name);

        // Relationship label
        nodeGroup.append("text")
          .attr("dy", 46)
          .attr("text-anchor", "middle")
          .attr("fill", COLORS.textMuted)
          .attr("font-size", "9px")
          .text(member.relationship);
      });

      // Connect to next generation if exists
      if (genIndex < generations.length - 1) {
        const nextGen = generations[genIndex + 1];
        const nextMembers = byGeneration[nextGen];
        const nextTotalWidth = (nextMembers.length - 1) * nodeSpacingX;
        const nextStartX = (width - nextTotalWidth) / 2;
        const nextY = (genIndex + 2) * nodeSpacingY + 40;

        // Center line down
        const centerX = width / 2;
        g.append("line")
          .attr("x1", centerX)
          .attr("y1", y + 20)
          .attr("x2", centerX)
          .attr("y2", nextY - 30)
          .attr("stroke", COLORS.link)
          .attr("stroke-width", 2);

        if (nextMembers.length > 1) {
          // Horizontal connector for next gen
          g.append("line")
            .attr("x1", nextStartX)
            .attr("y1", nextY - 30)
            .attr("x2", nextStartX + nextTotalWidth)
            .attr("y2", nextY - 30)
            .attr("stroke", COLORS.link)
            .attr("stroke-width", 2);
        }
      }
    });

  }, [descendants, rootName, rootId]);

  if (descendants.length === 0) {
    return <p className="text-[#555555]">No descendants yet</p>;
  }

  return (
    <div ref={containerRef} className="w-full overflow-x-auto">
      <svg ref={svgRef} className="w-full" style={{ minHeight: "250px" }}></svg>
    </div>
  );
}
