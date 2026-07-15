# SubstationOS Architecture Blueprint

Version: 1.0  
Status: Active  
Product phase: Alpha

---

## 1. Product Mission

SubstationOS è un Engineering Operating System progettato per EPC contractor, Project Engineer, Commissioning Engineer e Protection Engineer che operano su cabine primarie e sottostazioni elettriche.

Il prodotto deve:

- ridurre il tempo necessario per trovare informazioni;
- eliminare le duplicazioni dei dati;
- ridurre gli errori dovuti a documenti o revisioni errate;
- centralizzare engineering, commissioning e relay testing;
- trasformare i dati tecnici in informazioni operative;
- supportare decisioni rapide e verificabili.

---

## 2. Product Principles

Ogni funzionalità deve superare questi criteri:

1. È utile a un Commissioning Engineer?
2. È mantenibile tra almeno tre anni?
3. È sufficientemente curata per un SaaS enterprise?
4. Regge l’utilizzo da parte di un EPC con centinaia di ingegneri?
5. Riduce tempi morti, errori o complessità operativa?

Ogni milestone deve lasciare il software in uno stato dimostrabile.

---

## 3. Architectural Principles

### Backend owns business logic

Il frontend non deve calcolare:

- Health Score;
- stato di avanzamento;
- rischio;
- completezza documentale;
- readiness per SAT o FAT;
- priorità operative.

Queste informazioni devono essere prodotte dal backend.

### Frontend owns presentation logic

Il frontend deve occuparsi di:

- rendering;
- interazioni;
- responsive design;
- accessibilità;
- loading states;
- error states;
- feedback utente.

### Single source of truth

Ogni dato deve avere una sola fonte autorevole.

Esempi:

- il progetto è identificato dal record `Project`;
- il documento appartiene al progetto tramite `project_id`;
- le metriche derivano dai dati backend;
- le attività future saranno associate a un progetto.

### Domain-oriented development

Ogni nuovo modulo deve rappresentare un dominio reale del lavoro di engineering.

---

## 4. Current Domains

### Projects

Responsabilità:

- anagrafica della commessa;
- cliente;
- EPC;
- località;
- livello di tensione;
- stato;
- descrizione;
- contenitore degli altri domini.

### Documents

Responsabilità:

- upload;
- storage;
- metadati;
- formato;
- categoria;
- revisione;
- associazione al progetto;
- ricerca e filtraggio.

### Intelligence

Responsabilità futura:

- Project Health Score;
- KPI;
- completezza documentale;
- risk level;
- readiness;
- next action;
- project summary.

### Commissioning

Responsabilità futura:

- attività di commissioning;
- checklist;
- SAT;
- FAT;
- avanzamento;
- risultati;
- evidenze.

### Relay Testing

Responsabilità futura:

- relè;
- test plan;
- risultati Omicron e ISA;
- esito delle prove;
- anomalie;
- documentazione associata.

### Engineering

Responsabilità futura:

- schemi funzionali;
- schemi di cablaggio;
- liste cavi;
- revisioni;
- as-built;
- documentazione tecnica.

---

## 5. Backend Architecture

Struttura attuale:

```text
apps/backend/app
├── database
├── models
├── routers
├── schemas
├── services
└── main.py