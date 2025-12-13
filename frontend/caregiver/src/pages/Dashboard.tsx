import { Link } from 'react-router-dom';
import { StickyNote, Shield, Clock, Search, ArrowRight } from 'lucide-react';
import { useNotes } from '../hooks/useNotes';
import { useConstitution, usePendingChanges } from '../hooks/useConstitution';
import { NoteCard } from '../components/Note/NoteCard';
import { Loading } from '../components/Common/Loading';
import { LayerBadge } from '../components/Note/LayerBadge';

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  link: string;
  color: string;
}

function StatCard({ icon, label, value, link, color }: StatCardProps) {
  return (
    <Link
      to={link}
      className="bg-white rounded-lg shadow-sm border p-4 hover:shadow-md transition-shadow"
    >
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${color}`}>{icon}</div>
        <div>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{label}</p>
        </div>
      </div>
    </Link>
  );
}

export function DashboardPage() {
  const { data: notes, isLoading: notesLoading } = useNotes({ active_only: true });
  const { data: constitution, isLoading: constitutionLoading } = useConstitution();
  const { data: pendingChanges, isLoading: pendingLoading } = usePendingChanges();

  const isLoading = notesLoading || constitutionLoading || pendingLoading;

  // 统计数据
  const totalNotes = notes?.length || 0;
  const factNotes = notes?.filter((n) => n.layer === 'fact').length || 0;
  const sessionNotes = notes?.filter((n) => n.layer === 'session').length || 0;
  const constitutionCount = constitution?.length || 0;
  const pendingCount = pendingChanges?.length || 0;

  // 最近记忆条目（取前5条）
  const recentNotes = notes?.slice(0, 5) || [];

  if (isLoading) {
    return <Loading text="加载中..." />;
  }

  return (
    <div className="space-y-6">
      {/* 统计卡片 */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<StickyNote size={24} className="text-blue-600" />}
          label="记忆条目总数"
          value={totalNotes}
          link="/notes"
          color="bg-blue-50"
        />
        <StatCard
          icon={<Shield size={24} className="text-red-600" />}
          label="核心身份条目"
          value={constitutionCount}
          link="/constitution"
          color="bg-red-50"
        />
        <StatCard
          icon={<Clock size={24} className="text-yellow-600" />}
          label="待审批"
          value={pendingCount}
          link="/pending"
          color="bg-yellow-50"
        />
        <StatCard
          icon={<Search size={24} className="text-green-600" />}
          label="搜索"
          value="语义搜索"
          link="/search"
          color="bg-green-50"
        />
      </div>

      {/* 层级分布 */}
      <div className="bg-white rounded-lg shadow-sm border p-4">
        <h3 className="font-medium text-gray-900 mb-3">记忆层级分布</h3>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <LayerBadge layer="constitution" size="sm" />
            <span className="text-gray-600">{constitutionCount} 条</span>
          </div>
          <div className="flex items-center gap-2">
            <LayerBadge layer="fact" size="sm" />
            <span className="text-gray-600">{factNotes} 条</span>
          </div>
          <div className="flex items-center gap-2">
            <LayerBadge layer="session" size="sm" />
            <span className="text-gray-600">{sessionNotes} 条</span>
          </div>
        </div>
      </div>

      {/* 待审批提醒 */}
      {pendingCount > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Clock className="text-yellow-600" size={24} />
              <div>
                <p className="font-medium text-yellow-800">
                  有 {pendingCount} 条待审批的核心身份变更
                </p>
                <p className="text-sm text-yellow-700">
                  请及时处理，确保 AI 核心身份的准确性
                </p>
              </div>
            </div>
            <Link
              to="/pending"
              className="flex items-center gap-1 text-yellow-700 hover:text-yellow-800 font-medium"
            >
              去处理 <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      )}

      {/* 最近记忆条目 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-gray-900">最近记忆条目</h3>
          <Link
            to="/notes"
            className="flex items-center gap-1 text-blue-600 hover:text-blue-700 text-sm font-medium"
          >
            查看全部 <ArrowRight size={16} />
          </Link>
        </div>
        {recentNotes.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {recentNotes.map((note) => (
              <NoteCard key={note.id} note={note} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            还没有记忆条目，
            <Link to="/notes" className="text-blue-600 hover:underline">
              去创建一个
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
