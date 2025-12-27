import { useState, useEffect } from 'react';
import type { Memory } from '../types';
import { LAYER_CONFIG, CATEGORY_CONFIG } from '../types';
import { JsonViewer } from './JsonViewer';

interface SaveData {
  content?: string;
  session_id?: string;
  related_files?: string[];
}

interface MemoryDetailProps {
  memory: Memory;
  isOpen: boolean;
  onClose: () => void;
  onVerify?: (id: string) => void;
  onDelete?: (id: string) => void;
  onSave?: (id: string, data: SaveData) => Promise<boolean>;
  verifying?: boolean;
  saving?: boolean;
}

export function MemoryDetail({
  memory,
  isOpen,
  onClose,
  onVerify,
  onDelete,
  onSave,
  verifying,
  saving,
}: MemoryDetailProps) {
  const [showJson, setShowJson] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(memory.content);
  const [editingRelated, setEditingRelated] = useState(false);
  const [editSessionId, setEditSessionId] = useState(memory.session_id || '');
  const [editRelatedFiles, setEditRelatedFiles] = useState(
    memory.related_files?.join('\n') || ''
  );

  // Reset edit state when memory changes
  useEffect(() => {
    setEditContent(memory.content);
    setEditing(false);
    setEditSessionId(memory.session_id || '');
    setEditRelatedFiles(memory.related_files?.join('\n') || '');
    setEditingRelated(false);
  }, [memory.id, memory.content, memory.session_id, memory.related_files]);

  if (!isOpen) return null;

  const layerConfig = LAYER_CONFIG[memory.layer] || {
    label: memory.layer,
    color: 'bg-gray-500',
    shortLabel: '?',
  };
  const categoryConfig = memory.category ? CATEGORY_CONFIG[memory.category] : null;

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleSave = async () => {
    if (onSave && editContent !== memory.content) {
      const success = await onSave(memory.id, { content: editContent });
      if (success) {
        setEditing(false);
      }
    } else {
      setEditing(false);
    }
  };

  const handleCancel = () => {
    setEditContent(memory.content);
    setEditing(false);
  };

  const handleSaveRelated = async () => {
    if (onSave) {
      const relatedFilesArray = editRelatedFiles
        .split('\n')
        .map(f => f.trim())
        .filter(f => f.length > 0);

      const success = await onSave(memory.id, {
        session_id: editSessionId || undefined,
        related_files: relatedFilesArray.length > 0 ? relatedFilesArray : undefined,
      });
      if (success) {
        setEditingRelated(false);
      }
    } else {
      setEditingRelated(false);
    }
  };

  const handleCancelRelated = () => {
    setEditSessionId(memory.session_id || '');
    setEditRelatedFiles(memory.related_files?.join('\n') || '');
    setEditingRelated(false);
  };

  const hasChanges = editContent !== memory.content;
  const hasRelatedChanges =
    editSessionId !== (memory.session_id || '') ||
    editRelatedFiles !== (memory.related_files?.join('\n') || '');

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="detail-title"
      onClick={handleBackdropClick}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in" />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 id="detail-title" className="text-lg font-semibold text-gray-900">
            记忆详情
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5 overflow-y-auto max-h-[calc(90vh-180px)] space-y-6">
          {/* Basic Info Section */}
          <section>
            <h3 className="text-sm font-medium text-gray-500 mb-3">基础信息</h3>
            <div className="bg-gray-50 rounded-xl p-4 space-y-3">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">ID</span>
                  <p className="font-mono text-gray-900 text-xs mt-0.5">{memory.id}</p>
                </div>
                <div>
                  <span className="text-gray-500">层级</span>
                  <p className="mt-0.5">
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium text-white ${layerConfig.color}`}>
                      {layerConfig.shortLabel} {layerConfig.label.split(' ').pop()}
                    </span>
                  </p>
                </div>
                <div>
                  <span className="text-gray-500">分类</span>
                  <p className="text-gray-900 mt-0.5">
                    {categoryConfig ? (
                      <span className="inline-flex items-center gap-1">
                        {categoryConfig.emoji} {categoryConfig.label}
                      </span>
                    ) : (
                      <span className="text-gray-400">未分类</span>
                    )}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500">置信度</span>
                  <p className="mt-0.5">
                    {memory.confidence < 1 ? (
                      <span className="inline-flex items-center gap-1 text-amber-600">
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        {(memory.confidence * 100).toFixed(0)}%
                      </span>
                    ) : (
                      <span className="text-green-600">100%</span>
                    )}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500">创建时间</span>
                  <p className="text-gray-900 mt-0.5">{formatDateTime(memory.created_at)}</p>
                </div>
                <div>
                  <span className="text-gray-500">来源</span>
                  <p className="text-gray-900 mt-0.5 font-mono text-xs">
                    {(memory as unknown as Record<string, unknown>).created_by as string || (memory as unknown as Record<string, unknown>).source as string || 'caregiver'}
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Content Section */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-500">内容</h3>
              {onSave && !editing && (
                <button
                  onClick={() => setEditing(true)}
                  className="text-xs text-lime-600 hover:text-lime-700 flex items-center gap-1"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  编辑
                </button>
              )}
              {editing && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCancel}
                    className="text-xs text-gray-500 hover:text-gray-700"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving || !hasChanges}
                    className="text-xs text-lime-600 hover:text-lime-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                  >
                    {saving ? (
                      <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    ) : (
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                    保存
                  </button>
                </div>
              )}
            </div>
            <div className="bg-gray-50 rounded-xl p-4">
              {editing ? (
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="w-full min-h-[120px] text-gray-900 text-sm leading-relaxed bg-white border border-gray-200 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-lime-500 focus:border-transparent resize-y"
                  placeholder="输入记忆内容..."
                  autoFocus
                />
              ) : (
                <p className="text-gray-900 text-sm leading-relaxed whitespace-pre-wrap">
                  {memory.content}
                </p>
              )}
            </div>
          </section>

          {/* Related Info Section */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-500">关联信息</h3>
              {onSave && !editingRelated && (
                <button
                  onClick={() => setEditingRelated(true)}
                  className="text-xs text-lime-600 hover:text-lime-700 flex items-center gap-1"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  编辑
                </button>
              )}
              {editingRelated && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCancelRelated}
                    className="text-xs text-gray-500 hover:text-gray-700"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleSaveRelated}
                    disabled={saving || !hasRelatedChanges}
                    className="text-xs text-lime-600 hover:text-lime-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                  >
                    {saving ? (
                      <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    ) : (
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                    保存
                  </button>
                </div>
              )}
            </div>
            <div className="bg-gray-50 rounded-xl p-4 space-y-3">
              <div>
                <span className="text-xs text-gray-500">会话 ID</span>
                {editingRelated ? (
                  <input
                    type="text"
                    value={editSessionId}
                    onChange={(e) => setEditSessionId(e.target.value)}
                    placeholder="输入会话 ID..."
                    className="mt-1 w-full text-xs font-mono text-gray-700 bg-white border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-lime-500 focus:border-transparent"
                  />
                ) : (
                  <p className="mt-0.5">
                    {memory.session_id ? (
                      <code className="text-xs font-mono text-gray-700 bg-gray-100 px-2 py-0.5 rounded">
                        {memory.session_id}
                      </code>
                    ) : (
                      <span className="text-gray-400 text-sm">未设置</span>
                    )}
                  </p>
                )}
              </div>
              <div>
                <span className="text-xs text-gray-500">关联文件</span>
                {editingRelated ? (
                  <div className="mt-1">
                    <textarea
                      value={editRelatedFiles}
                      onChange={(e) => setEditRelatedFiles(e.target.value)}
                      placeholder="每行一个文件路径..."
                      rows={3}
                      className="w-full text-xs font-mono text-gray-700 bg-white border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-lime-500 focus:border-transparent resize-y"
                    />
                    <p className="text-xs text-gray-400 mt-1">每行输入一个文件路径</p>
                  </div>
                ) : (
                  <div className="mt-1">
                    {memory.related_files && memory.related_files.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {memory.related_files.map((file, idx) => (
                          <code
                            key={idx}
                            className="text-xs font-mono text-gray-700 bg-gray-100 px-2 py-0.5 rounded"
                          >
                            {file}
                          </code>
                        ))}
                      </div>
                    ) : (
                      <span className="text-gray-400 text-sm">未设置</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* JSON Section */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-500">JSON 原始数据</h3>
              <button
                onClick={() => setShowJson(!showJson)}
                className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
              >
                {showJson ? '收起' : '展开'}
                <svg
                  className={`w-4 h-4 transition-transform ${showJson ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
            {showJson && <JsonViewer data={memory} />}
          </section>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50/50">
          {/* Verify button - only show if confidence < 1 */}
          {memory.confidence < 1 && onVerify && (
            <button
              onClick={() => onVerify(memory.id)}
              disabled={verifying}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-lime-700 bg-lime-100 hover:bg-lime-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {verifying ? (
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              )}
              确认记忆
            </button>
          )}

          {/* Delete button */}
          {onDelete && (
            <button
              onClick={() => onDelete(memory.id)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-red-700 bg-red-100 hover:bg-red-200 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              删除
            </button>
          )}

          {/* Close button */}
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 transition-colors"
          >
            关闭
          </button>
        </div>
      </div>

      <style>{`
        @keyframes fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scale-in {
          from { opacity: 0; transform: scale(0.95) translateY(10px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        .animate-fade-in {
          animation: fade-in 0.15s ease-out;
        }
        .animate-scale-in {
          animation: scale-in 0.2s ease-out;
        }
      `}</style>
    </div>
  );
}
