import { useState, type ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { DemoBanner } from '../common/DemoBanner';

interface AppLayoutProps {
  children: ReactNode;
  showDemoBanner?: boolean;
}

export function AppLayout({ children, showDemoBanner = true }: AppLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app-container">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="main-wrapper">
        <Header onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <main className="content-area">
          {showDemoBanner && <DemoBanner />}
          {children}
        </main>
      </div>
    </div>
  );
}
