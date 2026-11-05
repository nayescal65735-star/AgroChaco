import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context';
import { DEMO_USERS } from '../services/mockData';
import { Sprout, Server, ShieldCheck, ArrowRight, BookOpen, AlertCircle } from 'lucide-react';

export function Login() {
  const { loginAsDemo, loginCustom } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleDemoSelect = (userId: string) => {
    loginAsDemo(userId);
    navigate('/');
  };

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setError('Por favor ingrese su correo institucional.');
      return;
    }
    loginCustom(email, email.split('@')[0], 'investigador');
    navigate('/');
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #17324D 0%, #0d1e30 60%, #152720 100%)',
        padding: '1.5rem',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '920px',
          background: '#ffffff',
          borderRadius: 'var(--radius-xl)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.45)',
          overflow: 'hidden',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
        }}
      >
        {/* Left Side: Scientific & Academic Branding */}
        <div
          style={{
            background: 'linear-gradient(160deg, #17324D 0%, #2F6B4F 100%)',
            color: '#ffffff',
            padding: '3rem 2.5rem',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            position: 'relative',
          }}
        >
          <div>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.65rem',
                padding: '0.4rem 0.85rem',
                background: 'rgba(255, 255, 255, 0.12)',
                borderRadius: '9999px',
                fontSize: '0.75rem',
                fontWeight: 700,
                color: 'var(--gold)',
                letterSpacing: '0.05em',
                marginBottom: '1.5rem',
              }}
            >
              <Server size={14} />
              COMPUTACIÓN PARALELA &amp; DISTRIBUIDA
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '1rem' }}>
              <div
                style={{
                  width: '52px',
                  height: '52px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--gold)',
                  color: 'var(--navy-dark)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 4px 14px rgba(215, 168, 75, 0.4)',
                }}
              >
                <Sprout size={32} />
              </div>
              <div>
                <h1 style={{ fontSize: '1.85rem', color: '#ffffff', lineHeight: 1.1 }}>AgroChaco</h1>
                <p style={{ color: '#c3d5e5', fontSize: '0.82rem', fontWeight: 500 }}>
                  Gran Chaco Boliviano (Tarija • Santa Cruz • Chuquisaca)
                </p>
              </div>
            </div>

            <p style={{ fontSize: '0.92rem', color: '#d8e5f1', lineHeight: 1.6, marginTop: '1.5rem' }}>
              Plataforma científica para la simulación numérica de déficit hídrico y estrés por sequía en cultivos de
              maíz (<em>Zea mays L.</em>), acelerada mediante arquitecturas paralelas OpenMP y clústeres distribuidos MPI.
            </p>

            <div style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', fontSize: '0.82rem', color: '#e2edf7' }}>
                <ShieldCheck size={16} color="var(--gold)" />
                <span>Modelo hidrológico FAO-56 Penman-Monteith</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', fontSize: '0.82rem', color: '#e2edf7' }}>
                <Server size={16} color="#34d399" />
                <span>Escalabilidad Fuerte y Débil en clúster HPC</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', fontSize: '0.82rem', color: '#e2edf7' }}>
                <BookOpen size={16} color="#93c5fd" />
                <span>Integración con FastAPI y PostgreSQL 16</span>
              </div>
            </div>
          </div>

          <div
            style={{
              paddingTop: '2rem',
              borderTop: '1px solid rgba(255, 255, 255, 0.15)',
              fontSize: '0.74rem',
              color: '#9cb5cb',
            }}
          >
            Proyecto de Investigación Aplicada • AgroChaco v1.0.0
          </div>
        </div>

        {/* Right Side: Login Form & Quick Demo Selector */}
        <div style={{ padding: '2.5rem', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <div style={{ marginBottom: '1.75rem' }}>
            <h2 style={{ fontSize: '1.4rem', color: 'var(--navy)' }}>Acceso al Sistema</h2>
            <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
              Seleccione una cuenta de demostración académica o ingrese sus credenciales.
            </p>
          </div>

          {/* Quick Demo Selector */}
          <div style={{ marginBottom: '1.75rem' }}>
            <div
              style={{
                fontSize: '0.75rem',
                textTransform: 'uppercase',
                fontWeight: 700,
                color: 'var(--text-muted)',
                marginBottom: '0.65rem',
                letterSpacing: '0.05em',
              }}
            >
              Acceso Rápido con Perfiles de Demostración:
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
              {DEMO_USERS.map((demoUser) => (
                <button
                  key={demoUser.id}
                  type="button"
                  onClick={() => handleDemoSelect(demoUser.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.85rem',
                    padding: '0.65rem 0.85rem',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-color)',
                    background: 'var(--bg-main)',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--agri-green)';
                    e.currentTarget.style.backgroundColor = 'var(--soft-green)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-color)';
                    e.currentTarget.style.backgroundColor = 'var(--bg-main)';
                  }}
                >
                  <img
                    src={demoUser.avatarUrl}
                    alt={demoUser.name}
                    style={{
                      width: '38px',
                      height: '38px',
                      borderRadius: '50%',
                      objectFit: 'cover',
                      border: '2px solid var(--soft-green-border)',
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--navy)' }}>
                      {demoUser.name}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {demoUser.role === 'investigador'
                        ? 'Investigadora Principal'
                        : demoUser.role === 'operador_hpc'
                        ? 'Operador HPC Clúster'
                        : 'Especialista Agrónomo'} • {demoUser.institution.split('-')[0]}
                    </div>
                  </div>
                  <ArrowRight size={16} color="var(--agri-green)" />
                </button>
              ))}
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              margin: '1rem 0',
              color: 'var(--text-muted)',
              fontSize: '0.78rem',
            }}
          >
            <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
            <span>o ingresar institucionalmente</span>
            <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
          </div>

          {error && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.65rem',
                borderRadius: 'var(--radius-sm)',
                background: '#fee2e2',
                color: 'var(--status-danger)',
                fontSize: '0.82rem',
                marginBottom: '1rem',
              }}
            >
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleCustomSubmit}>
            <div className="form-group">
              <label className="form-label" htmlFor="login-email">
                Correo Institucional
              </label>
              <input
                id="login-email"
                type="email"
                className="form-input"
                placeholder="investigador@agrochaco.edu.bo"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setError('');
                }}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="login-password">
                Contraseña
              </label>
              <input
                id="login-password"
                type="password"
                className="form-input"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '0.5rem' }}
            >
              Iniciar Sesión en AgroChaco
            </button>
          </form>

          <div
            style={{
              marginTop: '1.5rem',
              textAlign: 'center',
              fontSize: '0.74rem',
              color: 'var(--text-muted)',
            }}
          >
            Backend FastAPI: <code>http://localhost:8000</code> • PostgreSQL 16
          </div>
        </div>
      </div>
    </div>
  );
}
