import { useEffect } from 'react';
import { createPortal } from 'react-dom';

interface Props {
  message: string;
  onDismiss: () => void;
}

/** Top-center portal toast — auto-dismiss, click-to-dismiss, Escape optional. */
export function Toast({ message, onDismiss }: Props) {
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
      role="status"
      aria-live="polite"
      onClick={onDismiss}
    >
      {message}
    </div>,
    document.body,
  );
}
