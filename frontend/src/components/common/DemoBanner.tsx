import { AlertTriangle } from 'lucide-react';

interface DemoBannerProps {
  message?: string;
}

export function DemoBanner({
  message = 'Zonas, suelos, variedades y usuarios son catálogos DEMO de referencia. Las ejecuciones y métricas se obtienen de FastAPI/PostgreSQL cuando el backend está disponible.',
}: DemoBannerProps) {
  return (
    <div className="demo-banner">
      <div className="demo-banner-content">
        <AlertTriangle size={18} />
        <span>{message}</span>
      </div>
      <span className="system-tag">Datos Demo / Sintéticos</span>
    </div>
  );
}
