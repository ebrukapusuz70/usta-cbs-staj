/* Haritada seçilen boru veya vananın bilgilerini gösterir.
 * Silme isteğini MapView bileşenine geri iletir. */
import { STATUS_PRESENTATION } from "../config/statusConfig";
import type { FeatureInfo } from "../types/gis";

interface FeatureInfoPanelProps {
  feature: FeatureInfo | null;
  message: string;
  onClose: () => void;
  onRequestEdit?: (feature: FeatureInfo) => void;
  onRequestDelete?: (feature: FeatureInfo) => void;
}

const mutableSources = new Set(["user_created_stage4", "user_created_stage4_e2e"]);
const protectedPipeIds = new Set(["3464", "3465"]);

export function FeatureInfoPanel({ feature, message, onClose, onRequestEdit, onRequestDelete }: FeatureInfoPanelProps) {
  // İşlem düğmeleri kaynak allowlist'ine göre gösterilir; backend aynı kararı
  // PATCH/DELETE sırasında tekrar verdiği için bu yalnız arayüz kolaylığıdır.
  const protectedPipe = Boolean(
    feature?.layerKey === "gasPipes" && protectedPipeIds.has(feature.id),
  );
  const mutable = Boolean(
    feature
    && mutableSources.has(feature.source)
    && !protectedPipe,
  );
  return (
    <aside className="panel info-panel" aria-label="Nesne bilgisi">
      <div className="panel-title panel-title-row">
        <div>
          <span className="eyebrow">Nesne Bilgisi</span>
          <h2>{feature ? (feature.layerKey === "gasValves" ? "Gaz Vanası" : "Gaz Borusu") : "Seçim"}</h2>
        </div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="Kapat">
          x
        </button>
      </div>
      {!feature && <p className="empty-state">{message || "Haritada boru veya vana seçin."}</p>}
      {feature && (
        <dl className="feature-list">
          <div>
            <dt>ID</dt>
            <dd>{feature.id}</dd>
          </div>
          <div>
            <dt>Kod</dt>
            <dd>{feature.code}</dd>
          </div>
          <div>
            <dt>Tür</dt>
            <dd>{feature.type}</dd>
          </div>
          <div>
            <dt>Malzeme</dt>
            <dd>{feature.material}</dd>
          </div>
          <div>
            <dt>Çap</dt>
            <dd>{feature.diameter === "-" ? "-" : `${feature.diameter} mm`}</dd>
          </div>
          <div>
            <dt>Durum</dt>
            <dd className="status-value" style={{ color: STATUS_PRESENTATION[feature.status].color }}>
              {STATUS_PRESENTATION[feature.status].label}
            </dd>
          </div>
          {feature.layerKey === "gasPipes" && <><div><dt>Basınç Sınıfı</dt><dd>{feature.pressureLevel}</dd></div><div><dt>İşletme Basıncı</dt><dd>{feature.operatingPressure === "-" ? "-" : `${feature.operatingPressure} bar`}</dd></div><div><dt>Uzunluk</dt><dd>{feature.length === "-" ? "Geometriden hesaplanır" : `${feature.length} m`}</dd></div></>}
          <div><dt>Döşeme Yılı</dt><dd>{feature.installYear}</dd></div>
          <div><dt>İlçe</dt><dd>{feature.district}</dd></div>
          {feature.relatedPipeId && (
            <div>
              <dt>Bağlı Boru</dt>
              <dd>{feature.relatedPipeId}</dd>
            </div>
          )}
          {feature.operatorName && (
            <div>
              <dt>Operatör</dt>
              <dd>{feature.operatorName}</dd>
            </div>
          )}
          <div>
            <dt>Kaynak</dt>
            <dd>{feature.source}</dd>
          </div>
          <div className="synthetic-notice"><dt>Uyarı</dt><dd>{mutable ? feature.syntheticNotice : protectedPipe ? "Bu Stage 4 kaydı koruma altındadır ve değiştirilemez." : "Bu kayıt eğitim amacıyla oluşturulmuş temel demo verisidir ve değiştirilemez."}</dd></div>
          {mutable && onRequestEdit && onRequestDelete && (
            <div className="feature-action-row"><dt>İşlemler</dt><dd><button type="button" onClick={() => onRequestEdit(feature)} aria-label={`${feature.code} kaydını düzenle`}>Düzenle</button><button type="button" className="danger" onClick={() => onRequestDelete(feature)} aria-label={`${feature.code} kaydını sil`}>Sil</button></dd></div>
          )}
        </dl>
      )}
    </aside>
  );
}
