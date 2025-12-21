import { NavLink } from 'react-router-dom';
import { Home, StickyNote, Shield, Clock, Search, CheckSquare } from 'lucide-react';
import clsx from 'clsx';

const navItems = [
  { path: '/', label: '概览', icon: Home },
  { path: '/notes', label: '记忆条目', icon: StickyNote },
  { path: '/constitution', label: '核心身份', icon: Shield },
  { path: '/pending', label: '待审批', icon: Clock },
  { path: '/checklist', label: '清单', icon: CheckSquare },
  { path: '/search', label: '语义搜索', icon: Search },
];

export function Sidebar() {
  return (
    <aside className="w-64 bg-gray-900 text-white min-h-screen p-4">
      <div className="mb-8">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <span className="text-2xl">🧠</span>
          Memory Anchor
        </h1>
        <p className="text-gray-400 text-sm mt-1">AI 外挂海马体</p>
      </div>

      <nav className="space-y-1">
        {navItems.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-4 py-3 rounded-lg transition-colors',
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              )
            }
          >
            <Icon size={20} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
