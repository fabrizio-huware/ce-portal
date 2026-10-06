# Dashboard

Per admin e presale. Il viewer non vi accede (`403`). I numeri sono quelli del [motore di calcolo](formule.md), sui dati e le tariffe congelati nella versione. Ogni dashboard si esporta (`.../export?format=xlsx|csv`) e l'esportazione è registrata nello storico.

La dashboard del **singolo CE** (scheda KPI) è già nel dettaglio del CE (`GET /ce/{id}`, campo `calculation.kpis`) e nell'export.

## Portfolio — `GET /dashboard/portfolio`

Filtri: `date_from`, `date_to`, `client_id`, `business_unit`, `include_pipeline` (default `true`).

**Che CE si contano**
- **Approvati**: l'ultima versione approvata di ogni CE non eliminato.
- **Pipeline** (serie separata): l'ultima versione aperta (bozza, in approvazione, rifiutata) dei CE che **non hanno ancora nessuna versione approvata**.
- Una **revisione in corso** di un CE già approvato (per esempio una v2 in bozza) **non si somma**: il CE conta con la sua versione approvata, e le revisioni in corso sono indicate a parte (`revisions_in_progress`).
- Il filtro per periodo seleziona i CE come la ricerca: **periodo sovrapposto**, estremi inclusi.

**Cosa restituisce**: totali (numero di CE, ricavi, costi, margine, margine %, giornate) per approvati e pipeline; ripartizione per **cliente**, **business unit** ("Non indicata" se vuota) e **stato**; andamento per **mese**; elenco dei CE con i loro numeri.

**Totali interi e totali mensili**: le ripartizioni per cliente, business unit e stato usano i totali interi dei CE (contingency inclusa). La vista per mese usa gli importi mensili e **non include la contingency**: la somma dei mesi è quindi inferiore al totale di un CE con contingency, e la differenza è la contingency. Il periodo filtra anche i mesi mostrati.

L'export Excel ha un foglio per ogni tabella (Riepilogo, Per cliente, Per business unit, Per stato, Per mese, Elenco CE); il CSV contiene l'elenco dei CE.

## Carico risorse — `GET /dashboard/resources`

Filtri: `date_from`, `date_to`, `client_id`, `profile_id`, `employee_id`, `include_pipeline` (default `false`).

- **Periodo**: senza date, dal **mese corrente a 11 mesi dopo**. Massimo 36 mesi (`422` oltre).
- **Capacità del mese** = giorni lavorativi (lun-ven) meno quelli non lavorativi del **calendario generale** gestito dall'admin. È la stessa per tutti i CE: i giorni non lavorativi inseriti sul singolo CE non la cambiano.
- **FTE** = giorni del mese ÷ capacità (1 = 100%). Ore = giorni × 8.
- **Sovraccarico**: un collaboratore è sovraccarico in un mese se supera il **100% (1 FTE)**; esattamente 100% non lo è. L'avviso vale per i collaboratori, non per i profili (che raggruppano più persone).
- **Righe per collaboratore** e **righe per profilo**: le righe di CE senza collaboratore contano sul profilo (`unassigned_days`) ma non su un collaboratore.
- Con `include_pipeline=true` ogni cella separa `days_approved` e `days_pipeline`; FTE e avviso valgono sul totale. Conta sempre una sola versione per CE (l'ultima approvata; la pipeline come nel portfolio).
- I giorni mensili sono quelli dello staffing del motore: in modalità percentuali dalle % del CE, in modalità ore dalla ripartizione proporzionale ai giorni lavorativi.

L'export Excel ha i fogli Collaboratori (FTE per mese, con sfondo rosso oltre il 100%), Profili (giorni per mese) e Dati; il CSV è in formato lungo (una riga per collaboratore o profilo e mese con giornate).
