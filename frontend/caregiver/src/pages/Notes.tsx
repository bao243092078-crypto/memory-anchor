import { useState } from 'react';
import { Plus, StickyNote } from 'lucide-react';
import { useNotes, useCreateNote, useUpdateNote, useDeleteNote } from '../hooks/useNotes';
import type { Note, CreateNoteRequest, UpdateNoteRequest, NotesQueryParams } from '../types/note';
import { NoteCard } from '../components/Note/NoteCard';
import { NoteForm } from '../components/Note/NoteForm';
import { NoteFilters } from '../components/Note/NoteFilters';
import { Modal } from '../components/Common/Modal';
import { Button } from '../components/Common/Button';
import { Loading } from '../components/Common/Loading';
import { EmptyState } from '../components/Common/EmptyState';

export function NotesPage() {
  const [filters, setFilters] = useState<NotesQueryParams>({ active_only: true });
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingNote, setEditingNote] = useState<Note | null>(null);
  const [deletingNote, setDeletingNote] = useState<Note | null>(null);

  const { data: notes, isLoading, error } = useNotes(filters);
  const createMutation = useCreateNote();
  const updateMutation = useUpdateNote();
  const deleteMutation = useDeleteNote();

  const handleCreate = (data: CreateNoteRequest | UpdateNoteRequest) => {
    // 创建时content是必填的，所以这里可以安全转型
    createMutation.mutate(data as CreateNoteRequest, {
      onSuccess: () => setIsCreateModalOpen(false),
    });
  };

  const handleUpdate = (data: CreateNoteRequest | UpdateNoteRequest) => {
    if (!editingNote) return;
    updateMutation.mutate(
      { id: editingNote.id, note: data as UpdateNoteRequest },
      { onSuccess: () => setEditingNote(null) }
    );
  };

  const handleDelete = () => {
    if (!deletingNote) return;
    deleteMutation.mutate(deletingNote.id, {
      onSuccess: () => setDeletingNote(null),
    });
  };

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">加载记忆条目时出错，请稍后重试</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 顶部操作栏 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <NoteFilters filters={filters} onChange={setFilters} />
        <Button onClick={() => setIsCreateModalOpen(true)}>
          <Plus size={18} className="mr-1" />
          新建记忆条目
        </Button>
      </div>

      {/* 记忆条目列表 */}
      {isLoading ? (
        <Loading text="加载中..." />
      ) : notes && notes.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {notes.map((note) => (
            <NoteCard
              key={note.id}
              note={note}
              onEdit={setEditingNote}
              onDelete={setDeletingNote}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<StickyNote size={48} />}
          title="还没有记忆条目"
          description="创建第一条记忆条目，帮助 AI 记住重要信息"
          action={
            <Button onClick={() => setIsCreateModalOpen(true)}>
              <Plus size={18} className="mr-1" />
              新建记忆条目
            </Button>
          }
        />
      )}

      {/* 创建模态框 */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="新建记忆条目"
      >
        <NoteForm
          onSubmit={handleCreate}
          onCancel={() => setIsCreateModalOpen(false)}
          loading={createMutation.isPending}
        />
      </Modal>

      {/* 编辑模态框 */}
      <Modal
        isOpen={!!editingNote}
        onClose={() => setEditingNote(null)}
        title="编辑记忆条目"
      >
        {editingNote && (
          <NoteForm
            note={editingNote}
            onSubmit={handleUpdate}
            onCancel={() => setEditingNote(null)}
            loading={updateMutation.isPending}
          />
        )}
      </Modal>

      {/* 删除确认模态框 */}
      <Modal
        isOpen={!!deletingNote}
        onClose={() => setDeletingNote(null)}
        title="确认删除"
      >
        <div className="space-y-4">
          <p className="text-gray-600">
            确定要删除这条记忆条目吗？删除后可以在「全部」状态中找回。
          </p>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-800">{deletingNote?.content}</p>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setDeletingNote(null)}>
              取消
            </Button>
            <Button
              variant="danger"
              onClick={handleDelete}
              loading={deleteMutation.isPending}
            >
              确认删除
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
