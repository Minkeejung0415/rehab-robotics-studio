import type { DragEvent } from 'react';
import type { BlockDefinition } from '../../types/blocks';
import type { SignalType } from '../../types/signals';
import { categoryColor, signalColor } from '../../theme/tokens';

export const BLOCK_TYPE_MIME = 'application/x-rehab-robotics-block';

interface Props {
  def: BlockDefinition;
  onAdd: (type: string) => void;
}

export function LibraryItem({ def, onAdd }: Props) {
  const cColor = categoryColor[def.category];
  const dataType: SignalType | undefined = def.outputs[0]?.signalType ?? def.inputs[0]?.signalType;

  const handleDragStart = (event: DragEvent<HTMLDivElement>) => {
    if (event.target instanceof HTMLElement && event.target.closest('button')) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData(BLOCK_TYPE_MIME, def.type);
  };

  return (
    <div
      className="palette-item"
      title={def.description}
      draggable
      onDragStart={handleDragStart}
      onDoubleClick={() => onAdd(def.type)}
    >
      <span className="palette-icon" style={{ borderColor: cColor, background: cColor + '22' }}>
        <span style={{ background: cColor }} />
      </span>
      <span className="palette-item-main">
        <span className="palette-item-name">{def.name}</span>
        {dataType && (
          <span className="type-badge" style={{ color: signalColor[dataType], borderColor: signalColor[dataType] + '55' }}>
            {dataType}
          </span>
        )}
      </span>
      <button className="palette-add" onClick={() => onAdd(def.type)} title="Add to canvas">
        +
      </button>
    </div>
  );
}
