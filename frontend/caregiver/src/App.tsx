import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout/Layout';
import { DashboardPage } from './pages/Dashboard';
import { NotesPage } from './pages/Notes';
import { SearchPage } from './pages/Search';
import { ConstitutionPage } from './pages/Constitution';
import { PendingPage } from './pages/Pending';
import { ChecklistPage } from './pages/Checklist';

// 创建 QueryClient 实例
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1分钟
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="notes" element={<NotesPage />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="constitution" element={<ConstitutionPage />} />
            <Route path="pending" element={<PendingPage />} />
            <Route path="checklist" element={<ChecklistPage />} />
            {/* 未匹配路由重定向到首页 */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
