# Dashboard

Per admin, presale e responsabili di business unit. Il viewer non vi accede (`403`). Con la **visibilità per business unit** accesa, il Portfolio conta solo i CE che l'utente vede e il Carico risorse mostra solo le persone della sua business unit (con il carico di tutti i CE). I numeri sono quelli del [motore di calcolo](formule.md), sui dati e le tariffe congelati nella versione. Ogni dashboard si esporta (`.../export?format=xlsx|csv`) e l'esportazione è registrata nello storico.

La dashboard del **singolo CE** (scheda KPI) è già nel dettaglio del CE (`GET /ce/{id}`, campo `calculation.kpis`) e nell'export.

## Portfolio — `GET /dashboard/portfolio`

Filtri: `date_from`, `date_to`, `client_id`, `business_unit_id` (i CE che coinvolgono quella business unit; un CE con più business unit compare in ognuna), `business_unit` (testo sull'etichetta, resta per compatibilità), `include_pipeline` (default `true`).

**Che CE si contano**
- **Approvati**: l'ultima versione approvata di ogni CE non eliminato **senza esito**. Gli approvati con esito si dividono: **Close Won** (serie a parte, conta come approvato) e **Close Lost** (a parte, **non conta come approvato** né nella vista per mese). Il totale `confirmed` è «approvati senza esito + Close Won»: è quello dei riquadri «Ricavi, margine e giornate approvati».
- **Pipeline** (serie separata): l'ultima versione aperta (bozza, in approvazione, rifiutata) dei CE che **non hanno ancora nessuna versione approvata**.
- Una **revisione in corso** di un CE già approvato (per esempio una v2 in bozza) **non si somma**: il CE conta con la sua versione approvata, e le revisioni in corso sono indicate a parte (`revisions_in_progress`).
- Il filtro per periodo seleziona i CE come la ricerca: **periodo sovrapposto**, estremi inclusi.

**Cosa restituisce**: totali (numero di CE, ricavi, costi, margine, margine %, giornate) per approvati (`approved`, senza esito), Close Won (`won`), Close Lost (`lost`), `confirmed` (approvati + Close Won) e pipeline; ogni gruppo (cliente, business unit) ha anche `won` e `lost`, la vista per mese ha `won` (mai i Close Lost) e ogni voce dell'elenco ha `scope` = `approved`, `won`, `lost` o `pipeline`; ripartizione per **cliente**, **business unit** ("Non indicata" se vuota) e **stato**; andamento per **mese**; elenco dei CE con i loro numeri.

**Totali interi e totali mensili**: le ripartizioni per cliente, business unit e stato usano i totali interi dei CE (contingency inclusa). La vista per mese usa gli importi mensili e **non include la contingency**: la somma dei mesi è quindi inferiore al totale di un CE con contingency, e la differenza è la contingency. Il periodo filtra anche i mesi mostrati.

L'export Excel ha un foglio per ogni tabella (Riepilogo, Per cliente, Per business unit, Per stato, Per mese, Elenco CE); il CSV contiene l'elenco dei CE.

## Carico risorse — `GET /dashboard/resources`

Filtri: `date_from`, `date_to`, `client_id`, `profile_id`, `employee_id`, `practice_id`, `business_unit_id` (solo le persone di quella business unit), `project` (testo contenuto nel nome del progetto o nel codice del CE; con la visibilità accesa si cercano solo i CE che l'utente vede), `include_pipeline` (default `false`).

**Per business unit**: oltre alle practice c'è la sezione `business_units`: una riga per business unit con le persone che hanno impegno nel periodo e la percentuale (giorni ÷ persone × giorni lavorativi del mese), come per le practice. La business unit di un collaboratore è quella della sua practice **attuale**, per tutto il periodo. Le righe dei collaboratori e delle practice riportano `business_unit_name`. Nelle esportazioni: foglio Excel «Business unit» e colonna «Business unit» **in coda** nei dati.

- **Periodo**: senza date, dal **mese corrente a 11 mesi dopo**. Massimo 36 mesi (`422` oltre).
- **Capacità del mese** = giorni lavorativi (lun-ven) meno quelli non lavorativi del **calendario generale** gestito dall'admin. È la stessa per tutti i CE: i giorni non lavorativi inseriti sul singolo CE non la cambiano.
- **FTE** = giorni del mese ÷ capacità (1 = 100%). Ore = giorni × 8.
- **Sovraccarico**: un collaboratore è sovraccarico in un mese se supera il **100% (1 FTE)**; esattamente 100% non lo è. L'avviso vale per i collaboratori, non per i profili (che raggruppano più persone).
- **Righe per practice** (`practices`): si sommano le persone della practice che **hanno impegno nel periodo** (quelle che compaiono nelle righe dei collaboratori). **Percentuale** (`fte`) = giorni della practice ÷ (persone × capacità del mese), cioè la media dell'impegno di quelle persone; **sovraccarica** se supera il 100% (esattamente 100% no). `persons` è il numero di persone contate.
  - Una persona con impegno in **un solo mese** del periodo conta in **tutti** i mesi (abbassa la percentuale dei mesi in cui non ha impegno). Chi non ha impegno nel periodo non conta.
  - La practice è quella **attuale** del collaboratore, per tutto il periodo (nessuno storico).
  - Con `practice_id` restano solo le persone e le righe di quella practice; le righe di CE **senza collaboratore** non appartengono a nessuna practice e restano fuori (anche dai profili).
  - Le righe dei collaboratori hanno `practice_name`.
- **Righe per collaboratore** e **righe per profilo**: le righe di CE senza collaboratore contano sul profilo (`unassigned_days`) ma non su un collaboratore.
- Con `include_pipeline=true` ogni cella separa `days_approved` e `days_pipeline`; FTE e avviso valgono sul totale. Conta sempre una sola versione per CE (l'ultima approvata; la pipeline come nel portfolio).
- **Esito**: un CE **Close Lost non pesa** sul carico (esce dal calcolo, e dal numero di CE); un **Close Won pesa come un approvato**. Se l'esito viene tolto, il CE torna a pesare.
- I giorni mensili sono quelli dello staffing del motore: in modalità percentuali dalle % del CE, in modalità ore dalla ripartizione proporzionale ai giorni lavorativi.

L'export Excel ha i fogli Collaboratori (FTE per mese, con sfondo rosso oltre il 100%), **Practice** (persone con impegno e percentuale per mese), Profili (giorni per mese) e Dati; il CSV è in formato lungo (una riga per collaboratore, **practice** o profilo e mese con giornate). Le colonne **Practice** e **Persone** sono **in coda**: chi legge il file con le colonne di prima non si accorge di nulla. Per le righe delle practice la capacità è quella di una persona × le persone contate. L'esportazione accetta lo stesso filtro `practice_id`.
