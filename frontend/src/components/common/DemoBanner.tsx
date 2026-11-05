import { AlertTriangle } from 'lucide-react';

interface DemoBannerProps {
  message?: string;
}

export function DemoBanner({
  message = 'Entorno Académico AgroChaco: Los datos mostrados corresponden a simulaciones sintéticas calibradas para el Gran Chaco boliviano con propósitos de investigación computacional.',
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
