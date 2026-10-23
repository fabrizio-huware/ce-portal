# Collaudo sull'ambiente reale (passo 10)

Il collaudo risponde a una domanda: **il portale funziona sull'ambiente vero, con persone vere, e se qualcosa si rompe lo vediamo?** Si fa prima sul **test**; quando è tutto a posto si ripete (in forma ridotta) sulla **produzione** prima di usarla.

Si compone di quattro parti: un controllo automatico dell'ambiente, le prove nel browser, qualche prova di operatività e sicurezza, e il passaggio in produzione. In fondo c'è il [registro](#registro-del-collaudo) da compilare.

**Cosa serve**: `gcloud` autenticato sul progetto (ruolo almeno «Visualizzatore»), Python 3, e tre o quattro persone con un account Google dell'organizzazione per i ruoli di prova: un **amministratore**, due **presale** e un **viewer**.

---

## 1. Controllo automatico dell'ambiente

Legge lo stato reale su Google Cloud (non modifica nulla e non legge i valori dei segreti):

```bash
python3 infra/scripts/check_env.py --project ID-DEL-PROGETTO --env test     # oppure --env prod
```

Controlla in otto sezioni: servizio (pronto, immagine vera, configurazione, segreti da Secret Manager), database (acceso, backup, protezione), lavori (migrazioni riuscite, dati iniziali caricati, email), pianificazione, segreti, registro delle immagini, avvisi e controllo di raggiungibilità, e infine una prova di fumo sull'indirizzo pubblico.

| Simbolo | Significato |
|---|---|
| ✔ | a posto |
| ⚠ | da guardare, ma non blocca (per esempio «nessun backup ancora» nel primo giorno) |
| ✘ | da correggere prima di andare avanti. Il programma esce con errore e li ripete in fondo |

**Criterio di uscita**: nessun ✘. Gli ⚠ vanno letti uno a uno e annotati nel registro (alcuni sono attesi nel test, per esempio le email in modalità `console`).

Dopo ogni correzione si rilancia lo stesso comando. Per i rimedi ai messaggi più comuni vedi la tabella «Se qualcosa non va» di [deploy.md](deploy.md).

---

## 2. Prove funzionali nel browser

Si fanno sull'indirizzo del servizio, **con l'accesso Google vero**, usando i quattro ruoli (amministratore, presale, responsabile di business unit, viewer). Per ogni prova si segna ✔/✘ nel registro.

### A. Accesso e utenti
| # | Prova | Atteso |
|---|---|---|
| A1 | Apri l'indirizzo con il browser, senza essere entrato | si apre la pagina di accesso, con il pulsante «Accedi con Google» e **senza** il modulo di accesso simulato |
| A2 | Accedi con l'amministratore iniziale (`bootstrap_admin_email`) | entri; in alto vedi «Amministratore» e le voci Conti economici, Dashboard, Amministrazione |
| A3 | Da *Amministrazione → Utenti* crea due presale e un viewer | compaiono nell'elenco; ognuno riceve l'email di accesso (se `mail_backend = "mailjet"`) |
| A4 | Accedi con un account dell'organizzazione **non registrato** | «Utente non abilitato», nessuna sessione |
| A5 | Accedi con un account Google **personale** (gmail) | rifiutato (dominio non ammesso) |
| A6 | Disattiva un utente e prova a farlo entrare | non entra; chi era già dentro perde l'accesso alla prossima richiesta |
| A7 | Come amministratore, prova a togliere il ruolo all'unico admin | rifiutato, con il messaggio «deve restare almeno un amministratore» |
| A8 | Esci e rientra; chiudi la scheda e riaprila | la sessione non resta aperta oltre la scheda |

### B. Dati di base
| # | Prova | Atteso |
|---|---|---|
| B1 | *Listino*: controlla le tariffe 2026 | i 9 profili con prezzi e costi del tuo listino (caricati dal lavoro `seed`) |
| B2 | *Listino*: importa da CSV il listino del nuovo anno, prima con un errore di proposito | il controllo elenca l'errore per riga e **non importa nulla**; col file corretto mostra «N nuovi» e poi importa |
| B3 | *Collaboratori*: importa un CSV di prova | idem: controllo prima, scrittura solo alla conferma |
| B4 | *Calendario*: «Genera le festività» dell'anno, poi di nuovo | la seconda volta dice che erano già presenti; aggiungi una chiusura aziendale e importane una da CSV |
| B5 | *Clienti*: crea, modifica, disattiva | un cliente disattivato non compare più tra le scelte di un nuovo CE |

### C. Ciclo di vita del conto economico
| # | Prova | Atteso |
|---|---|---|
| C1 | Come presale crea un CE **a ore** con almeno due fasi e collaboratori | i totali in alto si aggiornano mentre scrivi |
| C2 | **Prova di calcolo di riferimento**: ricrea il CE del foglio `PS-BONGA-AI-PJT` (righe e fasi in `backend/tests/fixtures/ce_bonga.json`) | **468 ore, 47.162,50 € di ricavi, 20.200,00 € di costi, 26.962,50 € di margine (57,17%), 58,5 giornate**: gli stessi numeri del foglio |
| C3 | Crea un CE **a percentuali mensili** | i giorni sono % × giorni lavorativi del mese intero; cambiando le chiusure del mese i giorni cambiano |
| C4 | Incolla una colonna di ore copiata da Excel | le righe si riempiono, anche con la virgola decimale |
| C5 | Esci dall'editor con modifiche non salvate | compare l'avviso |
| C6 | Apri lo stesso CE in due schede, salva da una e poi dall'altra | la seconda dice che il CE è stato modificato e **non** sovrascrive |
| C7 | «Duplica come nuovo CE» | nuovo codice, stesse righe |
| C8 | Un presale prova a modificare il CE di un collega | non può: il messaggio dice che solo l'autore o un admin può |

### D. Approvazione ed email
| # | Prova | Atteso |
|---|---|---|
| D1 | Il presale «Invia in approvazione» un CE incompleto | non parte: l'elenco dei problemi è completo |
| D2 | Lo completa e lo invia | stato «In approvazione»; **l'amministratore riceve l'email** (solo il prezzo, mai costi o margini) |
| D3 | L'admin lo rifiuta con un motivo | il presale riceve l'email con il motivo; lo vede nel CE; lo corregge e lo reinvia |
| D4 | L'admin approva | il presale riceve l'email; il CE non è più modificabile |
| D5 | Il presale crea una **nuova versione** | l'admin riceve l'email; la versione approvata resta quella visibile ai viewer |
| D6 | *Amministrazione → Email* | tutte le email compaiono come «Inviata» con destinatario e oggetto; nessuna «Fallita» |
| D7 | Controlla la casella reale e la cartella spam | arrivano e **non** finiscono in spam (se sì: SPF/DKIM del dominio in Mailjet) |

### E. Esportazioni
| # | Prova | Atteso |
|---|---|---|
| E1 | Scarica l'**Excel completo** di un CE | si apre; le celle blu si modificano e i totali si ricalcolano (formule vive); fogli Riepilogo, Dettaglio, Fasi, Profili, Staffing, Tariffe, Note |
| E2 | Scarica il **PDF** completo e quello di riepilogo | leggibili, con il logo, orientamento corretto |
| E3 | Scarica il **CSV** | si apre in Excel italiano con le colonne giuste e i decimali con la virgola |
| E4 | Esporta l'elenco dei CE | contiene solo ciò che vedi con i filtri attivi |

### F. Dashboard
| # | Prova | Atteso |
|---|---|---|
| F1 | *Dashboard → Portfolio* | i ricavi degli approvati coincidono con la somma dei CE approvati; la pipeline è separata |
| F2 | *Carico risorse* con un CE che porta una persona oltre il 100% | la cella è rossa con ⚠ e il numero; la persona compare tra quelle in sovraccarico |
| F3 | Filtra per cliente, profilo, collaboratore, periodo | i numeri cambiano coerentemente |
| F4 | Esporta le due dashboard | Excel e CSV scaricati |

### G. Riservatezza del viewer
| # | Prova | Atteso |
|---|---|---|
| G1 | Accedi come viewer | vede solo i CE approvati e il riepilogo (giornate e ricavi per fase); **nessun costo, margine o riga** |
| G2 | Non vede «Dashboard» né «Amministrazione» | confermato; aprendo gli indirizzi a mano riceve un avviso |
| G3 | Esporta come viewer | file di riepilogo; apri l'Excel e controlla **ogni foglio**: nessun costo né margine |

### H. Dispositivi e prestazioni
| # | Prova | Atteso |
|---|---|---|
| H1 | Apri il portale da smartphone (e da un secondo browser) | si usa senza scorrere in orizzontale; i filtri stanno dietro il pulsante «Filtri» |
| H2 | Primo accesso dopo mezz'ora di inattività (servizio a zero istanze) | annota quanti secondi ci vogliono; se sono troppi, `min_instances = 1` |
| H3 | Navigazione normale | annota se qualche pagina è lenta (elenco, dashboard, export) |

### I. Business unit e visibilità
| # | Prova | Atteso |
|---|---|---|
| I1 | *Business unit*: crea le tue business unit; assegna le practice (*Practice*) e i presale e un responsabile (*Utenti*) | nei conteggi della scheda compaiono practice, collaboratori e persone di ciascuna; a una persona non si può assegnare «Da assegnare» |
| I2 | Crea un CE senza scegliere una business unit | il modulo lo rifiuta: «Scegli almeno una business unit coinvolta» |
| I3 | In un CE scegli un collaboratore di una business unit **non** coinvolta | compare l'avviso con «Aggiungi»; l'invio in approvazione è bloccato finché non coincidono |
| I4 | *Business unit* → «Assegna ai CE esistenti» | dice quanti CE ha aggiornato e quali restano senza; ripetendolo non cambia nulla |
| I5 | Con l'interruttore **spento**, due presale di business unit diverse aprono lo stesso CE | entrambi lo vedono, come prima |
| I6 | Guarda il rapporto dell'interruttore, poi accendilo | elenca CE senza business unit, presale senza business unit e practice in «Da assegnare»; chiede conferma se ci sono avvisi |
| I7 | Acceso: un presale apre l'elenco e il link di un CE che coinvolge **solo** un'altra business unit | non lo trova nell'elenco; il link dice «CE non trovato» |
| I8 | Acceso: lo stesso presale crea un CE per un'altra business unit | lo vede ancora (è l'autore); nell'elenco serve «Solo i miei CE» o «Tutte» |
| I9 | Un responsabile di una business unit coinvolta approva un CE in approvazione; poi prova un responsabile di un'altra | il primo approva (l'autore riceve l'email); il secondo non vede o non può approvare |
| I10 | Acceso: il presale apre il Carico risorse | vede solo le persone della sua business unit |
| I11 | Spegni l'interruttore | tutti tornano a vedere tutto |

---

## 3. Operatività e resilienza (una tantum)

Servono a sapere **in anticipo** cosa si fa quando qualcosa va storto. Si fanno sul test.

| # | Prova | Come | Atteso |
|---|---|---|---|
| R1 | Tornare a una revisione precedente | `gcloud run revisions list --service ce-portal-test …`, poi `gcloud run services update-traffic ce-portal-test --to-revisions=REVISIONE-VECCHIA=100 …`, infine di nuovo `--to-latest` | il portale risponde con la versione vecchia e poi con la nuova, senza perdere dati |
| R2 | **Ripristino del database da un backup** | `gcloud sql backups create --instance ce-portal-test-db`, poi clona (`gcloud sql instances clone ce-portal-test-db copia-prova`) e controlla i dati; elimina la copia | la copia contiene i dati; sai quanto ci vuole |
| R3 | Cambiare la chiave delle sessioni | nuova versione del segreto `…-jwt-secret` e nuovo avvio del servizio | tutti devono rifare l'accesso; poi il portale funziona |
| R4 | Mettere in pausa e riattivare le email | `gcloud scheduler jobs pause ce-portal-test-mail …`, poi `resume` | durante la pausa le email restano «In coda» in *Amministrazione → Email*; dopo la riattivazione partono |
| R5 | Cercare nei log | console → Cloud Run → servizio → Log; filtra per gravità `ERROR` | trovi una richiesta tua e capisci come cercare un errore |
| R6 | Provare gli avvisi | console → Monitoraggio → Canali di notifica → «Invia notifica di prova» | arriva l'email di prova all'indirizzo `alert_email` |
| R7 | Un rilascio sbagliato | fai un rilascio con una modifica volutamente rotta in un ramo di prova, oppure leggi i log di un rilascio in cui i controlli di fumo falliscono | il flusso si ferma e riporta il traffico alla revisione precedente |

## 4. Sicurezza (controlli rapidi)

| # | Prova | Atteso |
|---|---|---|
| S1 | `curl -sI https://INDIRIZZO/` | ci sono `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`; in produzione anche `Strict-Transport-Security` |
| S2 | `curl -s -o /dev/null -w '%{http_code}' https://INDIRIZZO/api/v1/ce` | `401` (l'API chiede l'accesso) |
| S3 | In produzione apri `/docs` e `/api/v1/openapi.json` | non mostrano la documentazione dell'API |
| S4 | Con la sessione del **viewer**, chiama `/api/v1/dashboard/portfolio` | `403` |
| S5 | `http://` invece di `https://` | Cloud Run risponde solo in `https` |
| S6 | Nessun accesso simulato: `curl -s https://INDIRIZZO/api/v1/config` | `"dev_login": false` |
| S7 | Controlla in *Secret Manager* chi può leggere i segreti | solo l'account di esecuzione e chi amministra il progetto |
| S8 | (facoltativo) analisi delle intestazioni con uno strumento pubblico | voto alto; la regola per Google Identity Services è voluta |

---

## 5. Passaggio in produzione

Si procede solo se il test ha superato le parti 1–4 senza ✘ aperti.

**Prima del rilascio**
1. `terraform apply` su `envs/prod` fatto; `terraform output github_variables` copiato nelle variabili del repository (le `PROD_…`).
2. L'**indirizzo di produzione** aggiunto alle *Origini JavaScript autorizzate* del Client ID (e il Client ID in `terraform.tfvars` di produzione).
3. Le chiavi di **Mailjet** nei due segreti di produzione; `mail_backend = "mailjet"`.
4. `bootstrap_admin_email` e `alert_email` impostati.
5. Nell'Environment `production` di GitHub: **revisori obbligatori** attivi.

**Rilascio**
6. Un rilascio da `main`: dopo il test il flusso si ferma in attesa di approvazione; approva solo dopo aver controllato il test.
7. Lancia **una sola volta** il lavoro `seed` di produzione (listino e festività).
8. `python3 infra/scripts/check_env.py --project ID-PROD --env prod`: **nessun ✘**.
9. Ripeti in produzione le prove **A1–A5, C1–C2, D2–D4, G1–G3, S1–S6** (non serve rifare tutto).
10. **Prova di ripristino**: fai un backup manuale e una copia di prova **prima** di inserire dati veri (R2), poi eliminala.

**Dati veri e apertura**
11. Importa collaboratori, listino dell'anno e chiusure aziendali; crea gli utenti.
12. Comunica l'indirizzo e chi è l'amministratore di riferimento.
13. Per la **prima settimana** controlla ogni giorno *Amministrazione → Email* e i log in cerca di `ERROR`; verifica che arrivi il primo backup notturno.

**Piano di ritorno**: se dopo l'apertura qualcosa va male, si torna alla revisione precedente (R1); i dati non si toccano. Un ripristino del database si fa sempre su una **copia**, mai sovrascrivendo (R2).

---

## Registro del collaudo

| Ambiente | Data | Chi | Controllo automatico (✘ aperti) | Prove A–H | Prove R/S | Esito |
|---|---|---|---|---|---|---|
| test | | | | | | ☐ pronto ☐ non pronto |
| produzione | | | | | | ☐ pronto ☐ non pronto |

Annota qui ogni ⚠ o ✘ con la decisione presa (corretto / accettato perché…):

| Prova | Problema | Decisione | Chi / quando |
|---|---|---|---|
| | | | |

**Il portale è pronto per l'uso quando**: il controllo automatico non ha ✘; le prove A, C, D, E, G sono tutte ✔ in produzione; le email arrivano; il backup e il ripristino sono stati provati; gli avvisi arrivano a una persona reale.
