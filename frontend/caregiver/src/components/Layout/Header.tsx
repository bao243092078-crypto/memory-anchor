import { Bell, User } from 'lucide-react';

interface HeaderProps {
  title: string;
}

export function Header({ title }: HeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-800">{title}</h2>

        <div className="flex items-center gap-4">
          <button className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg">
            <Bell size={20} />
          </button>
          <button className="flex items-center gap-2 text-gray-700 hover:bg-gray-100 px-3 py-2 rounded-lg">
            <User size={20} />
            <span className="text-sm">Admin</span>
          </button>
        </div>
      </div>
    </header>
  );
}
