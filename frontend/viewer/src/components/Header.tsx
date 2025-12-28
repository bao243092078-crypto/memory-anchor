import { useTranslation } from 'react-i18next';
import { ProjectSelector } from './ProjectSelector';
import { LanguageSwitcher } from './LanguageSwitcher';

export type ViewType = 'search' | 'timeline' | 'graph';

interface HeaderProps {
  memoryCount: number;
  isLoading?: boolean;
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
  currentProject: string;
  onProjectChange?: (projectId: string) => void;
}

export function Header({
  memoryCount,
  isLoading,
  currentView,
  onViewChange,
  currentProject,
  onProjectChange,
}: HeaderProps) {
  const { t } = useTranslation();

  return (
    <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-100">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="w-9 h-9 rounded-lg bg-gray-900 flex items-center justify-center">
                  <svg
                    className="w-5 h-5 text-lime-400"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M12 2L2 7l10 5 10-5-10-5z" />
                    <path d="M2 17l10 5 10-5" />
                    <path d="M2 12l10 5 10-5" />
                  </svg>
                </div>
                <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-lime-400 rounded-full border-2 border-white" />
              </div>
              <div>
                <h1 className="text-base font-semibold text-gray-900 tracking-tight">
                  {t('header.title')}
                </h1>
                <p className="text-[11px] text-gray-400 font-medium tracking-wide">
                  {t('header.subtitle')}
                </p>
              </div>
            </div>

            {/* Project Selector */}
            <div className="h-6 w-px bg-gray-200" />
            <ProjectSelector
              currentProject={currentProject}
              onProjectChange={onProjectChange}
            />
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => onViewChange('search')}
              className={`
                flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium
                transition-all duration-200
                ${currentView === 'search'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
                }
              `}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              {t('header.searchTab')}
            </button>
            <button
              onClick={() => onViewChange('timeline')}
              className={`
                flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium
                transition-all duration-200
                ${currentView === 'timeline'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
                }
              `}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              {t('header.timelineTab')}
            </button>
            <button
              onClick={() => onViewChange('graph')}
              className={`
                flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium
                transition-all duration-200
                ${currentView === 'graph'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
                }
              `}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <circle cx="19" cy="5" r="2" />
                <circle cx="5" cy="5" r="2" />
                <circle cx="5" cy="19" r="2" />
                <circle cx="19" cy="19" r="2" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9V6M12 15v3M9 12H6M15 12h3M10 10L7 7M14 14l3 3M10 14l-3 3M14 10l3-3" />
              </svg>
              {t('header.graphTab', '图谱')}
            </button>
          </div>

          {/* Stats & Actions */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-gray-400">{t('header.memoryCount')}</span>
              <span className={`
                inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5
                rounded-full text-xs font-semibold
                ${isLoading
                  ? 'bg-gray-100 text-gray-400 animate-pulse-subtle'
                  : 'bg-lime-100 text-lime-700'
                }
              `}>
                {isLoading ? '...' : memoryCount}
              </span>
            </div>

            <div className="h-4 w-px bg-gray-200" />

            {/* Language Switcher */}
            <LanguageSwitcher />

            <div className="h-4 w-px bg-gray-200" />

            <a
              href="https://github.com/anthropics/claude-code"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-gray-400 hover:text-gray-600 transition-colors flex items-center gap-1.5"
            >
              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
              </svg>
              {t('header.builtBy')}
            </a>
          </div>
        </div>
      </div>
    </header>
  );
}
