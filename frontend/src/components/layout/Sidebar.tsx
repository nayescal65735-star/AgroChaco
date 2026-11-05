import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  PlusCircle,
  PlayCircle,
  BarChart3,
  Zap,
  History,
  Settings,
  Sprout,
  X,
  Server,
} from 'lucide-react';
import { useSimulations } from '../../context';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { systemHealth, isExecutionActive } = useSimulations();

  const navItems = [
    {
      to: '/',
      label: 'Dashboard',
      icon: <LayoutDashboard size={19} />,
      badge: undefined,
    },
    {
      to: '/nueva-simulacion',
      label: 'Nueva Simulación',
      icon: <PlusCircle size={19} />,
      badge: 'HPC',
    },
    {
      to: '/ejecucion',
      label: 'Ejecución en Vivo',
      icon: <PlayCircle size={19} />,
      badge: isExecutionActive ? 'Activo' : undefined,
    },
    {
      to: '/resultados',
      label: 'Resultados & Análisis',
      icon: <BarChart3 size={19} />,
      badge: undefined,
    },
    {
      to: '/comparacion-rendimiento',
      label: 'Benchmark & Speedup',
      icon: <Zap size={19} />,
      badge: 'MPI/OMP',
    },
    {
      to: '/historial',
      label: 'Historial de Corridas',
      icon: <History size={19} />,
      badge: undefined,
    },
    {
      to: '/configuracion',
      label: 'Configuración del Sistema',
      icon: <Settings size={19} />,
      badge: undefined,
    },
  ];

  return (
    <>
      {isOpen && <div className="sidebar-backdrop" onClick={onClose} />}

      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="brand-icon-box">
            <Sprout size={24} />
          </div>
          <div className="brand-text" style={{ flex: 1 }}>
            <h1>AgroChaco</h1>
            <span>Simulador Paralelo</span>
          </div>
          <button
            type="button"
            className="menu-toggle-btn"
            style={{ color: '#ffffff', display: isOpen ? 'flex' : 'none' }}
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar-nav">
          <div className="sidebar-nav-heading">Módulos Científicos</div>

          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? 'active' : ''}`
              }
              onClick={onClose}
            >
              {item.icon}
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.badge && (
                <span
                  style={{
                    fontSize: '0.68rem',
                    padding: '0.1rem 0.45rem',
                    borderRadius: '9999px',
                    background: item.badge === 'Activo' ? 'var(--status-success)' : 'rgba(215, 168, 75, 0.25)',
                    color: item.badge === 'Activo' ? '#ffffff' : 'var(--gold)',
                    fontWeight: 700,
                  }}
                >
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-hpc-pill">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Server size={14} color="#34d399" />
              <span>Chaco HPC Cluster</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                {systemHealth.clusterNodes} Nodos
              </span>
              <div className="status-dot" />
            </div>
          </div>
          <div
            style={{
              fontSize: '0.68rem',
              color: '#64748b',
              marginTop: '0.5rem',
              textAlign: 'center',
            }}
          >
            OpenMP 4.5 • MPICH 4.1.2 • FAO-56
          </div>
        </div>
      </aside>
    </>
  );
}
