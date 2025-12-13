import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

const pageTitles: Record<string, string> = {
  '/': '概览',
  '/notes': '记忆条目',
  '/constitution': '核心身份',
  '/pending': '待审批',
  '/search': '语义搜索',
};

export function Layout() {
  const location = useLocation();
  const title = pageTitles[location.pathname] || '页面';

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header title={title} />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
