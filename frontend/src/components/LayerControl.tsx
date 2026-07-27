/* WMS katmanlarını açıp kapatan kontrol panelidir.
 * Katman adlarını appConfig dosyasından alır. */
import { appConfig } from "../config/appConfig";
import { STATUS_ORDER, STATUS_PRESENTATION } from "../config/statusConfig";
import type { LayerKey, LayerState } from "../types/gis";

interface LayerControlProps {
  layerState: LayerState;
  loadingLayers: LayerState;
  errors: Partial<Record<LayerKey, string>>;
  onToggle: (key: LayerKey) => void;
}

export function LayerControl({ layerState, loadingLayers, errors, onToggle }: LayerControlProps) {
  // Katman bilgisi tek yapılandırmadan alınır; ad ve renkler bileşene gömülmez.
  const layers = [appConfig.layers.gasPipes, appConfig.layers.gasValves];

  return (
    <section className="panel layer-panel" aria-label="Katmanlar">
      <div className="panel-title">
        <span className="status-dot" />
        <h2>Katmanlar</h2>
      </div>
      {layers.map((layer) => (
        <label className="layer-row" htmlFor={`layer-${layer.key}`} key={layer.key}>
          <input
            id={`layer-${layer.key}`}
            type="checkbox"
            checked={layerState[layer.key]}
            onChange={() => onToggle(layer.key)}
          />
          <span className="swatch" style={{ background: layer.color }} />
          <span>
            {layer.title}
            {loadingLayers[layer.key] && <small>Yükleniyor</small>}
            {errors[layer.key] && <small className="error-text">{errors[layer.key]}</small>}
          </span>
        </label>
      ))}
      <div className="legend-group" aria-label="Lejant">
        <div className="legend-title">Boru ve vana durumları</div>
        {STATUS_ORDER.map((status) => {
          const presentation = STATUS_PRESENTATION[status];
          return (
            <div className="legend-row" key={status}>
              <span className="legend-symbols" aria-hidden="true">
                <span className="line-swatch status-line" style={{ borderColor: presentation.color }} />
                <span className="point-swatch status-point" style={{ background: presentation.color }} />
              </span>
              {presentation.label}
            </div>
          );
        })}
        <small className="legend-help">Çizgi: boru · Daire: vana</small>
      </div>
    </section>
  );
}
