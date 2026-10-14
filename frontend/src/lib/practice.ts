/** Practice di sistema: la ricevono i collaboratori finché non se ne indica una. Non si rinomina né si disattiva. */
export const SYSTEM_PRACTICE = "Da assegnare";

export const isSystemPractice = (name: string): boolean => name.trim().toLowerCase() === SYSTEM_PRACTICE.toLowerCase();

type PracticeRef = { id: string; name: string; is_active: boolean };

/**
 * Practice che si possono scegliere per un collaboratore: quelle attive, più quella che ha già (anche se nel frattempo è
 * stata disattivata), altrimenti la scheda non potrebbe mostrarla né mantenerla. Il server rifiuta comunque una
 * practice disattivata nuova, quindi non va offerta.
 */
export function choosablePractices<T extends PracticeRef>(practices: T[], currentId: string): T[] {
  return practices.filter((p) => p.is_active || p.id === currentId);
}
