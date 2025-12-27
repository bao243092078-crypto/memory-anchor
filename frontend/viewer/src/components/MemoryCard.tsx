import type { Memory } from '../types';
import { LAYER_CONFIG, CATEGORY_CONFIG } from '../types';

interface MemoryCardProps {
  memory: Memory;
  index?: number;
}

export function MemoryCard({ memory, index = 0 }: MemoryCardProps) {
  const layerConfig = LAYER_CONFIG[memory.layer] || {
    label: memory.layer,
    color: 'bg-gray-500',
    shortLabel: '?',
  };
  const categoryConfig = memory.category ? CATEGORY_CONFIG[memory.category] : null;

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
      return '昨天';
    } else if (days < 7) {
      return `${days} 天前`;
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    }
  };

  return (
    <article
      className={`
        group relative
        bg-white rounded-2xl border border-gray-100
        hover:border-gray-200 hover:shadow-lg hover:shadow-gray-100/50
        transition-all duration-300 ease-out
        animate-fade-in-up opacity-0
      `}
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      {/* Layer indicator bar */}
      <div
        className={`absolute top-0 left-0 right-0 h-1 rounded-t-2xl ${layerConfig.color}`}
        style={{ opacity: 0.8 }}
      />

      <div className="p-5 pt-6">
        {/* Header: Tags */}
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          {/* Layer tag */}
          <span className={`
            inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg
            text-xs font-semibold text-white ${layerConfig.color}
          `}>
            <span className="text-[10px] opacity-80">{layerConfig.shortLabel}</span>
            <span className="opacity-90">{layerConfig.label.split(' ').pop()}</span>
          </span>

          {/* Category tag */}
          {categoryConfig && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-gray-600 bg-gray-100">
              <span>{categoryConfig.emoji}</span>
              <span className="capitalize">{categoryConfig.label}</span>
            </span>
          )}

          {/* Score badge */}
          {memory.score !== undefined && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold text-lime-700 bg-lime-100">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3 3a1 1 0 000 2v8a2 2 0 002 2h2.586l-1.293 1.293a1 1 0 101.414 1.414L10 15.414l2.293 2.293a1 1 0 001.414-1.414L12.414 15H15a2 2 0 002-2V5a1 1 0 100-2H3zm11.707 4.707a1 1 0 00-1.414-1.414L10 9.586 8.707 8.293a1 1 0 00-1.414 0l-2 2a1 1 0 101.414 1.414L8 10.414l1.293 1.293a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              {(memory.score * 100).toFixed(0)}% 匹配
            </span>
          )}

          {/* Confidence indicator */}
          {memory.confidence < 1 && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-amber-700 bg-amber-50">
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              {(memory.confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>

        {/* Content */}
        <p className="text-gray-700 text-sm leading-relaxed mb-4 whitespace-pre-wrap">
          {memory.content}
        </p>

        {/* Traceability section */}
        {(memory.session_id || memory.related_files?.length) && (
          <div className="mt-4 pt-4 border-t border-gray-50 space-y-2">
            {memory.session_id && (
              <div className="flex items-center gap-2 text-xs">
                <span className="flex items-center gap-1.5 text-gray-400">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  会话
                </span>
                <code className="px-2 py-0.5 bg-gray-50 rounded text-gray-600 font-mono text-[11px]">
                  {memory.session_id}
                </code>
              </div>
            )}

            {memory.related_files && memory.related_files.length > 0 && (
              <div className="flex items-start gap-2 text-xs">
                <span className="flex items-center gap-1.5 text-gray-400 mt-0.5">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  关联文件
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {memory.related_files.map((file, idx) => (
                    <code
                      key={idx}
                      className="px-2 py-0.5 bg-gray-50 rounded text-gray-600 font-mono text-[11px] hover:bg-gray-100 transition-colors cursor-default"
                    >
                      {file.split('/').pop()}
                    </code>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-50">
          <span className="text-xs text-gray-400">
            {formatDate(memory.created_at)}
          </span>
          <span className="text-[10px] text-gray-300 font-mono tracking-tight">
            {memory.id.slice(0, 8)}
          </span>
        </div>
      </div>
    </article>
  );
}
