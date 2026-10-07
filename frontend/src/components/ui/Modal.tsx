import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** Finestra di dialogo (elemento <dialog> nativo: tiene il focus al suo interno e si chiude con Esc). */
export function Modal({ open, title, onClose, children, footer, wide }: { open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  // Le finestre stanno nel body, non dentro il contenuto: così un modulo non finisce mai dentro un altro modulo.
  return createPortal(
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      // React fa risalire l'evento di chiusura dalle finestre annidate: ognuna deve reagire solo alla propria
      onClose={(e) => e.target === e.currentTarget && onClose()}
      onClick={(e) => e.target === ref.current && onClose()}
      className={`m-auto w-[calc(100vw-2rem)] ${wide ? "max-w-2xl" : "max-w-lg"} rounded-2xl border border-line bg-paper p-0 text-ink shadow-xl backdrop:bg-ink/50`}
    >
      {open && (
        <div className="p-6">
          <h2 id={titleId} className="text-xl font-medium tracking-normal">{title}</h2>
          <div className="mt-4 space-y-4 text-sm">{children}</div>
          {footer && <div className="mt-6 flex flex-wrap justify-end gap-2">{footer}</div>}
        </div>
      )}
    </dialog>,
    document.body,
  );
}
