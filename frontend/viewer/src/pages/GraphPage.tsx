import { useEffect, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import * as d3 from 'd3';
import { getGraphData } from '../api/memory';
import type { GraphData, GraphNode, MemoryLayer, NoteCategory } from '../types';

// Layer colors matching backend
const LAYER_COLORS: Record<string, string> = {
  identity_schema: '#ef4444',
  constitution: '#ef4444',
  active_context: '#f97316',
  event_log: '#3b82f6',
  session: '#3b82f6',
  verified_fact: '#22c55e',
  fact: '#22c55e',
  operational_knowledge: '#a855f7',
};

const LAYER_LABELS: Record<string, string> = {
  identity_schema: 'L0 身份图式',
  event_log: 'L2 事件日志',
  verified_fact: 'L3 验证事实',
  operational_knowledge: 'L4 操作知识',
};

const LAYER_OPTIONS: MemoryLayer[] = ['identity_schema', 'event_log', 'verified_fact', 'operational_knowledge'];
const CATEGORY_OPTIONS: NoteCategory[] = ['person', 'place', 'event', 'item', 'routine'];

const CATEGORY_LABELS: Record<string, string> = {
  person: '👤 人物',
  place: '📍 地点',
  event: '📅 事件',
  item: '📦 物品',
  routine: '🔄 习惯',
};

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx?: number;
  vy?: number;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  source: SimNode;
  target: SimNode;
  edge_type: string;
  weight: number;
  color: string;
  dashed: boolean;
}

export function GraphPage() {
  const { t } = useTranslation();
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [limit, setLimit] = useState(100);
  const [selectedLayers, setSelectedLayers] = useState<MemoryLayer[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<NoteCategory[]>([]);
  const [showFilters, setShowFilters] = useState(false);

  // Fetch graph data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getGraphData({
        limit,
        layers: selectedLayers.length > 0 ? selectedLayers : undefined,
        categories: selectedCategories.length > 0 ? selectedCategories : undefined,
      });
      setGraphData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, [limit, selectedLayers, selectedCategories]);

  const toggleLayer = (layer: MemoryLayer) => {
    setSelectedLayers(prev =>
      prev.includes(layer)
        ? prev.filter(l => l !== layer)
        : [...prev, layer]
    );
  };

  const toggleCategory = (category: NoteCategory) => {
    setSelectedCategories(prev =>
      prev.includes(category)
        ? prev.filter(c => c !== category)
        : [...prev, category]
    );
  };

  const clearFilters = () => {
    setSelectedLayers([]);
    setSelectedCategories([]);
  };

  const hasFilters = selectedLayers.length > 0 || selectedCategories.length > 0;

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // D3 force simulation
  useEffect(() => {
    if (!graphData || !svgRef.current || !containerRef.current) return;
    if (graphData.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight || 600;

    // Clear previous content
    svg.selectAll('*').remove();

    // Create zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg
      .attr('width', width)
      .attr('height', height)
      .call(zoom);

    const g = svg.append('g');

    // Prepare data for simulation
    const nodes: SimNode[] = graphData.nodes.map(n => ({
      ...n,
      x: Math.random() * width,
      y: Math.random() * height,
    }));

    const nodeById = new Map(nodes.map(n => [n.id, n]));

    const links: SimLink[] = graphData.edges
      .map(e => {
        const source = nodeById.get(typeof e.source === 'string' ? e.source : e.source.id);
        const target = nodeById.get(typeof e.target === 'string' ? e.target : e.target.id);
        if (!source || !target) return null;
        return {
          source,
          target,
          edge_type: e.edge_type,
          weight: e.weight,
          color: e.color,
          dashed: e.dashed,
        } as SimLink;
      })
      .filter((l): l is SimLink => l !== null);

    // Create force simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink<SimNode, SimLink>(links)
        .id(d => d.id)
        .distance(80)
        .strength(d => d.weight * 0.5))
      .force('charge', d3.forceManyBody().strength(-150))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => (d as SimNode).size + 5));

    // Draw links
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', d => d.color)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', d => Math.max(1, d.weight * 2))
      .attr('stroke-dasharray', d => d.dashed ? '4,4' : 'none');

    // Draw nodes
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', d => d.size)
      .attr('fill', d => d.color)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .call(d3.drag<SVGCircleElement, SimNode>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }) as any)
      .on('click', (_, d) => {
        setSelectedNode(d);
      })
      .on('mouseover', function() {
        d3.select(this).attr('stroke', '#84cc16').attr('stroke-width', 3);
      })
      .on('mouseout', function() {
        d3.select(this).attr('stroke', '#fff').attr('stroke-width', 2);
      });

    // Add tooltips
    node.append('title')
      .text(d => d.label);

    // Draw labels for larger nodes
    const labels = g.append('g')
      .attr('class', 'labels')
      .selectAll('text')
      .data(nodes.filter(n => n.size >= 12))
      .join('text')
      .text(d => d.label.substring(0, 15) + (d.label.length > 15 ? '...' : ''))
      .attr('font-size', 10)
      .attr('fill', '#374151')
      .attr('text-anchor', 'middle')
      .attr('dy', d => d.size + 12)
      .style('pointer-events', 'none');

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);

      labels
        .attr('x', d => d.x)
        .attr('y', d => d.y);
    });

    // Cleanup
    return () => {
      simulation.stop();
    };
  }, [graphData]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            {t('graph.title', '记忆图谱')}
          </h2>
          <p className="text-sm text-gray-500">
            {t('graph.subtitle', '可视化记忆之间的关联')}
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Filter toggle */}
          <div className="relative">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`
                flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm
                ${hasFilters ? 'bg-lime-100 text-lime-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}
              `}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
              {t('filter.title', '筛选器')}
              {hasFilters && (
                <span className="ml-1 px-1.5 py-0.5 bg-lime-500 text-white text-xs rounded-full">
                  {selectedLayers.length + selectedCategories.length}
                </span>
              )}
            </button>

            {/* Filter dropdown */}
            {showFilters && (
              <div className="absolute right-0 mt-2 w-72 bg-white rounded-lg shadow-lg border border-gray-200 z-50 p-4 space-y-4">
                {/* Layer filter */}
                <div>
                  <div className="text-xs font-medium text-gray-500 mb-2">{t('filter.layers', '记忆层级')}</div>
                  <div className="flex flex-wrap gap-1.5">
                    {LAYER_OPTIONS.map(layer => (
                      <button
                        key={layer}
                        onClick={() => toggleLayer(layer)}
                        className={`
                          px-2 py-1 text-xs rounded-md flex items-center gap-1
                          ${selectedLayers.includes(layer)
                            ? 'text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          }
                        `}
                        style={selectedLayers.includes(layer) ? { backgroundColor: LAYER_COLORS[layer] } : undefined}
                      >
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: LAYER_COLORS[layer] }}
                        />
                        {LAYER_LABELS[layer]}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Category filter */}
                <div>
                  <div className="text-xs font-medium text-gray-500 mb-2">{t('filter.categories', '分类')}</div>
                  <div className="flex flex-wrap gap-1.5">
                    {CATEGORY_OPTIONS.map(category => (
                      <button
                        key={category}
                        onClick={() => toggleCategory(category)}
                        className={`
                          px-2 py-1 text-xs rounded-md
                          ${selectedCategories.includes(category)
                            ? 'bg-gray-900 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          }
                        `}
                      >
                        {CATEGORY_LABELS[category]}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Clear filters */}
                {hasFilters && (
                  <button
                    onClick={clearFilters}
                    className="w-full text-xs text-gray-500 hover:text-gray-700 py-1"
                  >
                    {t('filter.clearFilters', '清除筛选')}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Limit selector */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">
              {t('graph.maxNodes', '最大节点数')}
            </label>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="rounded-md border-gray-300 text-sm"
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
            </select>
          </div>

          {/* Refresh button */}
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 bg-gray-900 text-white text-sm rounded-md hover:bg-gray-800 disabled:opacity-50"
          >
            {loading ? t('common.loading', '加载中...') : t('common.refresh', '刷新')}
          </button>
        </div>
      </div>

      {/* Stats */}
      {graphData && (
        <div className="flex items-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-gray-500">{t('graph.nodes', '节点')}</span>
            <span className="font-medium">{graphData.node_count}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-500">{t('graph.edges', '边')}</span>
            <span className="font-medium">{graphData.edge_count}</span>
          </div>
          <div className="h-4 w-px bg-gray-200" />
          {/* Layer legend */}
          {Object.entries(graphData.layer_stats).map(([layer, count]) => (
            <div key={layer} className="flex items-center gap-1.5">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: LAYER_COLORS[layer] || '#888' }}
              />
              <span className="text-gray-600">
                {LAYER_LABELS[layer] || layer}: {count}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Graph container */}
      <div
        ref={containerRef}
        className="relative bg-white rounded-xl border border-gray-200 overflow-hidden"
        style={{ height: '600px' }}
      >
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80">
            <div className="flex items-center gap-2 text-gray-500">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              {t('common.loading', '加载中...')}
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <p className="text-red-500 mb-2">{error}</p>
              <button
                onClick={fetchData}
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                {t('common.retry', '重试')}
              </button>
            </div>
          </div>
        )}

        {!loading && !error && graphData?.nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-500">
            {t('graph.noData', '暂无记忆数据')}
          </div>
        )}

        <svg ref={svgRef} className="w-full h-full" />

        {/* Instructions */}
        <div className="absolute bottom-4 left-4 text-xs text-gray-400 space-y-1">
          <p>{t('graph.dragHint', '拖拽节点移动位置')}</p>
          <p>{t('graph.scrollHint', '滚轮缩放，拖拽画布平移')}</p>
          <p>{t('graph.clickHint', '点击节点查看详情')}</p>
        </div>

        {/* Edge type legend */}
        <div className="absolute bottom-4 right-4 bg-white/90 rounded-lg p-2 text-xs space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-gray-400" style={{ borderStyle: 'dashed' }} />
            <span className="text-gray-600">{t('graph.timeSequence', '时间序列')}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-lime-500" />
            <span className="text-gray-600">{t('graph.sharedCategory', '共享分类')}</span>
          </div>
        </div>
      </div>

      {/* Selected node detail */}
      {selectedNode && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">
                {t('graph.nodeDetail', '记忆详情')}
              </h3>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-4 space-y-3 overflow-y-auto max-h-[60vh]">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: selectedNode.color }}
                />
                <span className="text-sm font-medium text-gray-700">
                  {LAYER_LABELS[selectedNode.layer] || selectedNode.layer}
                </span>
                {selectedNode.category && (
                  <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">
                    {selectedNode.category}
                  </span>
                )}
              </div>
              <p className="text-gray-900 whitespace-pre-wrap">
                {selectedNode.content}
              </p>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>
                  {t('graph.confidence', '置信度')}: {(selectedNode.confidence * 100).toFixed(0)}%
                </span>
                <span>
                  {t('graph.createdAt', '创建时间')}: {new Date(selectedNode.created_at).toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
