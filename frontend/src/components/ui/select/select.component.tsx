/**
 * A small, self-contained dropdown select.
 *
 * Native `<select>` popups are rendered by the OS and can't be sized or styled
 * to match a compact UI — they look oversized against the page. This component
 * replaces the popup with a portalled, fixed-positioned listbox we fully
 * control (page typography, hover/selected states, a scroll cap), while keeping
 * standard select semantics: a labelled trigger, keyboard navigation, and
 * close-on-outside-interaction.
 *
 * Portalled to `document.body` with `position: fixed` so it escapes any
 * `overflow: hidden`/stacking-context clipping (per the product guidance on
 * dropdowns in scroll containers).
 *
 * @module Select
 */
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface SelectOption {
  value: string;
  label: string;
  /** Optional trailing count, right-aligned and quiet (e.g. per-source totals). */
  count?: number;
}

interface Rect {
  left: number;
  top: number;
  bottom: number;
  width: number;
}

const MENU_MAX_HEIGHT = 288; // px — ~8 rows before scrolling
const MENU_GAP = 4; // px between trigger and menu

export function Select({
  label,
  value,
  options,
  onChange,
  disabled,
  className,
}: {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<Rect | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const listboxId = useId();

  const selected = options.find((o) => o.value === value) ?? options[0];
  const selectedIndex = Math.max(
    options.findIndex((o) => o.value === value),
    0,
  );

  const measure = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    setRect({ left: r.left, top: r.top, bottom: r.bottom, width: r.width });
  }, []);

  const openMenu = useCallback(() => {
    if (disabled) return;
    measure();
    setActiveIndex(selectedIndex);
    setOpen(true);
  }, [disabled, measure, selectedIndex]);

  const closeMenu = useCallback(() => {
    setOpen(false);
    setActiveIndex(-1);
  }, []);

  const commit = useCallback(
    (option: SelectOption) => {
      onChange(option.value);
      closeMenu();
      triggerRef.current?.focus();
    },
    [onChange, closeMenu],
  );

  // Reposition while open; close on outside pointer / scroll / resize.
  useLayoutEffect(() => {
    if (!open) return;
    measure();
    const onScroll = () => measure();
    const onResize = () => measure();
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        !triggerRef.current?.contains(target) &&
        !menuRef.current?.contains(target)
      ) {
        closeMenu();
      }
    };
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onResize);
    document.addEventListener('pointerdown', onPointerDown, true);
    return () => {
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onResize);
      document.removeEventListener('pointerdown', onPointerDown, true);
    };
  }, [open, measure, closeMenu]);

  // Keep the highlighted option in view as the user arrows through.
  useEffect(() => {
    if (!open || activeIndex < 0) return;
    const node = menuRef.current?.children[activeIndex] as
      | HTMLElement
      | undefined;
    node?.scrollIntoView({ block: 'nearest' });
  }, [open, activeIndex]);

  function onTriggerKeyDown(event: React.KeyboardEvent) {
    if (!open) {
      if (['Enter', ' ', 'ArrowDown', 'ArrowUp'].includes(event.key)) {
        event.preventDefault();
        openMenu();
      }
      return;
    }
    switch (event.key) {
      case 'Escape':
        event.preventDefault();
        closeMenu();
        break;
      case 'ArrowDown':
        event.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, options.length - 1));
        break;
      case 'ArrowUp':
        event.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        break;
      case 'Home':
        event.preventDefault();
        setActiveIndex(0);
        break;
      case 'End':
        event.preventDefault();
        setActiveIndex(options.length - 1);
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        if (activeIndex >= 0) commit(options[activeIndex]);
        break;
      case 'Tab':
        closeMenu();
        break;
    }
  }

  const menuStyle: React.CSSProperties = rect
    ? {
        position: 'fixed',
        left: rect.left,
        top: rect.bottom + MENU_GAP,
        width: rect.width,
        maxHeight: MENU_MAX_HEIGHT,
      }
    : { display: 'none' };

  return (
    <div className={cn('space-y-1.5', className)}>
      <label
        id={`${listboxId}-label`}
        className="block text-xs font-medium text-muted-foreground"
      >
        {label}
      </label>
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-labelledby={`${listboxId}-label`}
        disabled={disabled}
        onClick={() => (open ? closeMenu() : openMenu())}
        onKeyDown={onTriggerKeyDown}
        className={cn(
          'flex h-10 w-full items-center justify-between gap-2 rounded-md border border-input bg-background pl-3 pr-2.5 text-sm',
          'ring-offset-background transition-colors hover:bg-secondary/40',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          'disabled:cursor-not-allowed disabled:opacity-50',
          open && 'ring-2 ring-ring',
        )}
      >
        <span className="truncate text-left">{selected?.label}</span>
        <ChevronDown
          className={cn(
            'size-4 shrink-0 text-muted-foreground transition-transform duration-150',
            open && 'rotate-180',
          )}
          aria-hidden="true"
        />
      </button>

      {open &&
        createPortal(
          <ul
            ref={menuRef}
            id={listboxId}
            role="listbox"
            aria-labelledby={`${listboxId}-label`}
            style={menuStyle}
            className="qpg-select-menu z-50 overflow-auto rounded-md border bg-background p-1 shadow-lg outline-none"
          >
            {options.map((option, index) => {
              const isSelected = option.value === value;
              const isActive = index === activeIndex;
              return (
                <li
                  key={option.value || '__all__'}
                  role="option"
                  aria-selected={isSelected}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => commit(option)}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm',
                    isActive
                      ? 'bg-secondary text-foreground'
                      : 'text-foreground',
                  )}
                >
                  <Check
                    className={cn(
                      'size-4 shrink-0',
                      isSelected ? 'opacity-100' : 'opacity-0',
                    )}
                    aria-hidden="true"
                  />
                  <span className="flex-1 truncate">{option.label}</span>
                  {option.count !== undefined && (
                    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                      {option.count.toLocaleString()}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>,
          document.body,
        )}
    </div>
  );
}
