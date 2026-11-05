import { useState } from 'react';
import { Menu, Wifi, WifiOff, LogOut, User as UserIcon, RefreshCw } from 'lucide-react';
import { useAuth, useSimulations } from '../../context';
import { useNavigate } from 'react-router-dom';

interface HeaderProps {
  onToggleSidebar: () => void;
}

export function Header({ onToggleSidebar }: HeaderProps) {
  const { user, logout } = useAuth();
  const { systemHealth, refreshSystemHealth } = useSimulations();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const navigate = useNavigate();

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refreshSystemHealth();
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isOnline = systemHealth.backend === 'online';

  return (
    <header className="top-header">
      <div className="header-left">
        <button
          type="button"
          className="menu-toggle-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle navigation menu"
        >
          <Menu size={22} />
        </button>

        <div className="system-title-container">
          <h2>
            AgroChaco
            <span className="system-tag">HPC Gran Chaco</span>
          </h2>
          <div className="system-subtitle">
            Simulador Paralelo &amp; Distribuido • Estrés Hídrico en Zea Mays
          </div>
        </div>
      </div>

      <div className="header-right">
        {/* Backend & DB Health status badge */}
        <div
          className={`backend-indicator-badge ${isOnline ? 'online' : 'offline'}`}
          title={`FastAPI: ${systemHealth.backend} | DB PostgreSQL 16: ${systemHealth.database} | Nodos: ${systemHealth.clusterNodes}`}
        >
          {isOnline ? <Wifi size={14} /> : <WifiOff size={14} />}
          <span>{isOnline ? 'FastAPI Conectado' : 'Modo Standalone / Demo'}</span>
          <button
            type="button"
            onClick={handleRefresh}
            title="Verificar conexión con backend FastAPI"
            style={{ display: 'inline-flex', padding: '2px', color: 'inherit' }}
          >
            <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* User profile with dropdown */}
        {user ? (
          <div className="user-profile-widget" onClick={() => setIsDropdownOpen(!isDropdownOpen)}>
            {user.avatarUrl ? (
              <img src={user.avatarUrl} alt={user.name} className="user-avatar" />
            ) : (
              <div className="user-avatar">
                {user.name.charAt(0).toUpperCase()}
              </div>
            )}
            <div className="user-meta" style={{ display: 'none', minWidth: '100px' }}>
              <span className="user-name">{user.name.split(' ')[0]}</span>
              <span className="user-role-badge">{user.role.toUpperCase()}</span>
            </div>

            {isDropdownOpen && (
              <div
                className="profile-dropdown"
                onClick={(e) => e.stopPropagation()}
              >
                <div style={{ padding: '0.6rem 0.8rem', borderBottom: '1px solid var(--border-light)' }}>
                  <div style={{ fontWeight: 700, color: 'var(--navy)', fontSize: '0.9rem' }}>{user.name}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{user.email}</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--agri-green)', marginTop: '0.2rem', fontWeight: 600 }}>
                    {user.institution}
                  </div>
                </div>

                <button
                  type="button"
                  className="profile-dropdown-item"
                  onClick={() => {
                    setIsDropdownOpen(false);
                    navigate('/configuracion');
                  }}
                >
                  <UserIcon size={16} />
                  <span>Perfil &amp; Ajustes HPC</span>
                </button>

                <button
                  type="button"
                  className="profile-dropdown-item danger"
                  onClick={handleLogout}
                >
                  <LogOut size={16} />
                  <span>Cerrar sesión</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => navigate('/login')}
          >
            Iniciar sesión
          </button>
        )}
      </div>
    </header>
  );
}
