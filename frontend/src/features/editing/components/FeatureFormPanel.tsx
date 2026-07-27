/* Çizilen nesnenin türüne göre vana veya boru formunu açar.
 * Form sonucunu MapView bileşenine iletir. */
import type { DraftFeature, GasPipeCreatePayload, GasValveCreatePayload } from "../types/editing";
import { PipeForm } from "./PipeForm";
import { ValveForm } from "./ValveForm";

interface Props { draft: DraftFeature; pending: boolean; onPipeSubmit: (payload: GasPipeCreatePayload) => void; onValveSubmit: (payload: GasValveCreatePayload) => void; onCancel: () => void; }

export function FeatureFormPanel(props: Props) {
  return <aside className="panel feature-form-panel" aria-label="Yeni kayıt formu">
    {props.draft.layerKey === "gasPipes"
      ? <PipeForm draft={props.draft} pending={props.pending} onSubmit={props.onPipeSubmit} onCancel={props.onCancel}/>
      : <ValveForm draft={props.draft} pending={props.pending} onSubmit={props.onValveSubmit} onCancel={props.onCancel}/>} 
  </aside>;
}
