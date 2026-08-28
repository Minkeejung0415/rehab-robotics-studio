/** Reusable keyboard-aware context menu; feature-specific actions are supplied by callers. */
import { Fragment, useEffect, useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

export interface ContextMenuItem {
  id: string;
  label: string;
  danger?: boolean;
  separatorBefore?: boolean;
  onSelect: () => void;
}

interface Props {
  x: number;
  y: number;
  items: ContextMenuItem[];
  onClose: () => void;
}

/** Fixed-position portal context menu with viewport clamp and dismiss handlers. */
export function ContextMenu({ x, y, items, onClose }: Props) {
  const menuRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const el = menuRef.current;
    if (!el) return;
    const pad = 4;
    const rect = el.getBoundingClientRect();
    let left = x;
    let top = y;
    if (left + rect.width > window.innerWidth - pad) {
      left = Math.max(pad, window.innerWidth - rect.width - pad);
    }
    if (top + rect.height > window.innerHeight - pad) {
      top = Math.max(pad, window.innerHeight - rect.height - pad);
    }
    if (left < pad) left = pad;
    if (top < pad) top = pad;
    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
  }, [x, y, items]);

  useEffect(() => {
    menuRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
        return;
      }

      const el = menuRef.current;
      if (!el) return;
      const menuitems = Array.from(
        el.querySelectorAll<HTMLElement>('[role="menuitem"]'),
      );
      if (menuitems.length === 0) return;

      const currentIndex = menuitems.indexOf(document.activeElement as HTMLElement);

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        const next = currentIndex < 0 ? 0 : (currentIndex + 1) % menuitems.length;
        menuitems[next]?.focus();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        const prev =
          currentIndex < 0
            ? menuitems.length - 1
            : (currentIndex - 1 + menuitems.length) % menuitems.length;
        menuitems[prev]?.focus();
      } else if (event.key === 'Home') {
        event.preventDefault();
        menuitems[0]?.focus();
      } else if (event.key === 'End') {
        event.preventDefault();
        menuitems[menuitems.length - 1]?.focus();
      }
    };
    const handlePointerDown = (event: PointerEvent) => {
      const el = menuRef.current;
      if (el && !el.contains(event.target as Node)) onClose();
    };
    const handleDismiss = () => onClose();
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('pointerdown', handlePointerDown);
    window.addEventListener('scroll', handleDismiss, true);
    window.addEventListener('resize', handleDismiss);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('pointerdown', handlePointerDown);
      window.removeEventListener('scroll', handleDismiss, true);
      window.removeEventListener('resize', handleDismiss);
    };
  }, [onClose]);

  return createPortal(
    <div
      ref={menuRef}
      className="context-menu"
      role="menu"
      tabIndex={-1}
      style={{ left: x, top: y }}
    >
      {items.map((item) => (
        <Fragment key={item.id}>
          {item.separatorBefore && <div className="context-menu-sep" role="separator" />}
          <button
            type="button"
            role="menuitem"
            className={`context-menu-item${item.danger ? ' is-danger' : ''}`}
            onClick={() => {
              item.onSelect();
              onClose();
            }}
          >
            {item.label}
          </button>
        </Fragment>
      ))}
    </div>,
    document.body,
  );
}
