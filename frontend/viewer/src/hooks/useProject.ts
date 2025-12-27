import { useState, useEffect, useCallback } from 'react';
import { getCurrentProject } from '../api/memory';

export interface UseProjectResult {
  currentProject: string;
  projectType: string;
  loading: boolean;
  error: string | null;
  switchProject: (projectId: string) => void;
}

export function useProject(): UseProjectResult {
  const [currentProject, setCurrentProject] = useState<string>('default');
  const [projectType, setProjectType] = useState<string>('ai-development');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load current project on mount
  useEffect(() => {
    async function loadProject() {
      setLoading(true);
      setError(null);
      try {
        const data = await getCurrentProject();
        setCurrentProject(data.project_id);
        setProjectType(data.project_type);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load project');
        // Fallback to default
        setCurrentProject('default');
      } finally {
        setLoading(false);
      }
    }
    loadProject();
  }, []);

  const switchProject = useCallback((projectId: string) => {
    // Show info message about switching
    // Since we can't actually switch at runtime (requires env var change),
    // we show a notification
    const message = `要切换到项目 "${projectId}"，请设置环境变量 MCP_MEMORY_PROJECT_ID="${projectId}" 并重启服务。`;

    // Create and show a toast notification
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 max-w-md p-4 bg-gray-900 text-white rounded-xl shadow-2xl z-[100] animate-fade-in';
    toast.innerHTML = `
      <div class="flex items-start gap-3">
        <svg class="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div>
          <p class="text-sm font-medium text-gray-100">切换项目需要重启服务</p>
          <p class="text-xs text-gray-400 mt-1">${message}</p>
          <div class="mt-3 flex gap-2">
            <button onclick="navigator.clipboard.writeText('MCP_MEMORY_PROJECT_ID=${projectId}'); this.textContent='已复制!'" class="px-2 py-1 text-xs font-medium bg-gray-800 hover:bg-gray-700 rounded text-gray-200 transition-colors">
              复制环境变量
            </button>
            <button onclick="this.closest('.fixed').remove()" class="px-2 py-1 text-xs font-medium text-gray-400 hover:text-gray-200 transition-colors">
              关闭
            </button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(toast);

    // Auto-remove after 10 seconds
    setTimeout(() => {
      if (toast.parentElement) {
        toast.remove();
      }
    }, 10000);
  }, []);

  return {
    currentProject,
    projectType,
    loading,
    error,
    switchProject,
  };
}
