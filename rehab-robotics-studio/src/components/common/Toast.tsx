import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { normalizeLiveKneeReason } from '../../data/liveKneeAngle';

export const OPEN_SIM_TOOLBAR_ACTION_ORDER = [
  'Calibrate',
  'Clear cal',
  'Open visualizer',
  'Save',
] as const;

type CommandResult = { success: boolean; message: string };

interface VisualizerControllerDependencies {
  request: () => Promise<CommandResult>;
  onBusyChange: (busy: boolean) => void;
  onFailure: (reason: string, alertMessage: string) => void;
}

export interface VisualizerRequestController {
  open(): Promise<CommandResult | null>;
  isPending(): boolean;
}

export function visualizerFailureAlert(reason: unknown): {
  reason: string;
  message: string;
} {
  const safeReason = normalizeLiveKneeReason(
    reason,
    'OpenSim visualizer could not open',
  );
  return {
    reason: safeReason,
    message: `OpenSim visualizer could not open: ${safeReason}. Check the OpenSim runtime, then retry.`,
  };
}

/** Pure request seam: one in-flight call, deterministic settlement, and retry. */
export function createVisualizerRequestController(
  dependencies: VisualizerControllerDependencies,
): VisualizerRequestController {
  let pending = false;

  return {
    async open() {
      if (pending) return null;
      pending = true;
      dependencies.onBusyChange(true);
      try {
        const result = await dependencies.request();
        if (!result.success) {
          const failure = visualizerFailureAlert(result.message);
          dependencies.onFailure(failure.reason, failure.message);
          return { success: false, message: failure.reason };
        }
        return result;
      } catch (error) {
        const failure = visualizerFailureAlert(
          error instanceof Error ? error.message : error,
        );
        dependencies.onFailure(failure.reason, failure.message);
        return { success: false, message: failure.reason };
      } finally {
        pending = false;
        dependencies.onBusyChange(false);
      }
    },
    isPending: () => pending,
  };
}

interface Props {
  message: string;
  onDismiss: () => void;
  tone?: 'status' | 'error';
}

/** Top-center portal toast — auto-dismiss, click-to-dismiss, Escape optional. */
export function Toast({ message, onDismiss, tone = 'status' }: Props) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(), 2500);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onDismiss();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onDismiss]);

  return createPortal(
    <div
      className="toast"
      role={tone === 'error' ? 'alert' : 'status'}
      aria-live={tone === 'error' ? 'assertive' : 'polite'}
      style={tone === 'error' ? { borderColor: '#ec5a5a', color: '#ec5a5a' } : undefined}
      onClick={onDismiss}
    >
      {message}
    </div>,
    document.body,
  );
}
