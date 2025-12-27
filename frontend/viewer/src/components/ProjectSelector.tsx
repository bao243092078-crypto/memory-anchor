import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { ProjectInfo } from '../types';
import { PROJECT_TYPE_CONFIG } from '../types';
import { listProjects } from '../api/memory';

interface ProjectSelectorProps {
  currentProject: string;
  onProjectChange?: (projectId: string) => void;
}

export function ProjectSelector({ currentProject, onProjectChange }: ProjectSelectorProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Load projects on mount
  useEffect(() => {
    async function loadProjects() {
      setLoading(true);
      setError(null);
      try {
        const data = await listProjects();
        setProjects(data.projects);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load projects');
      } finally {
        setLoading(false);
      }
    }
    loadProjects();
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentProjectInfo = projects.find(p => p.id === currentProject);
  const typeConfig = PROJECT_TYPE_CONFIG[currentProjectInfo?.type || 'ai-development'] || PROJECT_TYPE_CONFIG['ai-development'];

  const handleSelect = (projectId: string) => {
    if (projectId !== currentProject) {
      onProjectChange?.(projectId);
    }
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-all focus:outline-none focus:ring-2 focus:ring-lime-500/20"
      >
        <span className="text-base">{typeConfig.emoji}</span>
        <span className="max-w-[120px] truncate">
          {currentProjectInfo?.name || currentProject}
        </span>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-72 bg-white rounded-xl border border-gray-200 shadow-xl z-50 animate-fade-in overflow-hidden">
          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50">
            <h3 className="text-sm font-semibold text-gray-900">{t('project.switchProject')}</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {t('project.projectCount', { count: projects.length })}
            </p>
          </div>

          {/* Projects list */}
          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <svg className="w-5 h-5 text-gray-400 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
            ) : error ? (
              <div className="px-4 py-6 text-center">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            ) : projects.length === 0 ? (
              <div className="px-4 py-6 text-center">
                <p className="text-sm text-gray-500">{t('project.noProjects')}</p>
              </div>
            ) : (
              <div className="py-1">
                {projects.map((project) => {
                  const projTypeConfig = PROJECT_TYPE_CONFIG[project.type] || PROJECT_TYPE_CONFIG['ai-development'];
                  const isSelected = project.id === currentProject;

                  return (
                    <button
                      key={project.id}
                      onClick={() => handleSelect(project.id)}
                      className={`
                        w-full flex items-center gap-3 px-4 py-3 text-left
                        transition-colors
                        ${isSelected
                          ? 'bg-lime-50 text-lime-900'
                          : 'hover:bg-gray-50 text-gray-700'
                        }
                      `}
                    >
                      {/* Type emoji */}
                      <span className="text-lg">{projTypeConfig.emoji}</span>

                      {/* Project info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">{project.name}</span>
                          {isSelected && (
                            <span className="flex-shrink-0 w-1.5 h-1.5 bg-lime-500 rounded-full" />
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-gray-400 truncate">{project.id}</span>
                          {project.has_constitution && (
                            <span className="flex-shrink-0 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 bg-amber-100 rounded">
                              {t('project.constitution')}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Checkmark for selected */}
                      {isSelected && (
                        <svg className="w-4 h-4 text-lime-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Footer hint */}
          <div className="px-4 py-3 border-t border-gray-100 bg-gray-50/50">
            <p className="text-xs text-gray-500">
              {t('project.restartHint')}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
