# Ottimizzare i file Markdown — cosa esiste, e cosa ho adottato

*Ricerca del 2026-09-07, a supporto di `mdcheck.py`, `ctxbudget.py`,
`~/.claude/rules/markdown.md` e delle skill `writing-docs` e
`compressing-context`. Ogni voce ha un verdetto: **adottato**, **adattato** o
**scartato**, con la ragione. Le fonti sono in fondo.*

**In breve.** Il pattern che conta si chiama *progressive disclosure* ed è
quello che avevo già applicato senza chiamarlo così: un indice leggero in testa,
il contenuto pieno solo quando serve. La documentazione ufficiale di Anthropic
dà anche una **soglia numerica** — oltre ~100 righe un file di riferimento vuole
un indice — e un limite per `CLAUDE.md` (**sotto le 200 righe**). Gli strumenti
maturi esistono ma sono tarati per team di documentazione con CI dedicata:
portano dipendenze e ~50 regole quasi tutte cosmetiche, quindi ne ho preso i
due controlli che contano e lasciato il resto. La seconda passata ha aggiunto i
tre meccanismi di Claude Code che rendono *automatica* la disciplina — regole a
percorso, skill con template, commenti HTML scartati dal contesto — e ha
misurato che un hook di tipo `prompt` non è filtrabile per percorso e blocca il
turno quando il modello risponde in prosa: scartato dopo un solo tentativo. La
terza passata ha cercato strumenti per la **dieta sistematica** dei file sempre
caricati: nessuno fa da solo ciò che serve, quindi la dieta è una skill con
misura prima/dopo (`ctxbudget.py`) e un test-manifesto che prova che nessuna
regola è sparita.

## Indice

- [I verdetti](#i-verdetti) — la tabella: cosa è entrato, cosa è stato adattato, cosa è fuori e perché
- [La dieta sistematica](#la-dieta-sistematica-cosa-fa-da-solo-e-cosa-no) — perché è una skill con misura e manifesto, non uno strumento
- [Le due metà](#le-due-metà-e-perché-la-distinzione-è-la-cosa-più-importante) — meccanica (decidibile) contro giudizio (no)
- [Fonti](#fonti) · [Storico](#storico)

## I verdetti

| Tecnica | Verdetto | Perché |
|---|---|---|
| **Progressive disclosure** (indice in testa, dettaglio a richiesta) | **Adottato** | È il pattern su cui sono costruite le Agent Skills: all'avvio si caricano solo i metadati, il corpo si legge quando serve. Applicato agli indici di `MILESTONES.md`, `SPEC.md`, `KNOWN_DEVIATIONS.md` e ai due referti lunghi |
| **Indice per i file oltre ~100 righe** | **Adattato** (soglia a 200) | La regola ufficiale esiste perché chi legge campionando la testa deve comunque vedere tutta la portata del file. Ho alzato la soglia a 200 per djmeta: a 100 righe fioccavano segnalazioni su documenti che si leggono benissimo interi |
| **La riga d'indice come risposta, non come rimando** | **Adottato** | Non viene dalla letteratura: è una lezione del progetto. Un indice che elenca titoli costringe comunque ad aprire la sezione; uno che dice *cosa* ha consegnato una milestone risponde da solo nel 90% dei casi |
| **`markdownlint` MD051** (link fragment) e **MD024** (titoli duplicati) | **Adattato** | Sono i due controlli che colgono difetti reali, e li ho riscritti in 40 righe di stdlib. MD024 però l'ho reso **condizionale**: segnala una collisione solo se un link ci punta davvero — nella forma incondizionata sparava 6 volte su djmeta e decine su appunti costruiti con sezioni ricorrenti |
| **`markdownlint` (tutto il resto)** | **Scartato** | ~50 regole, la gran parte cosmetiche (stile dei trattini di lista, righe vuote). Dipendenza Node in progetti Python e di tesi, rumore garantito, e un linter rumoroso è un linter che si disattiva |
| **`PyMarkdownLnt`** (linter puro Python) | **Scartato per l'hook, valido per la CI** | Ottimo strumento e senza Node, ma resta una dipendenza da installare: l'hook globale deve partire con qualunque `python` in PATH, in sette progetti eterogenei. E non sa fare i controlli che qui contano di più — link relativi, specchio indice/corpo |
| **`Vale`** (linter di prosa e terminologia) | **Scartato** | Fatto per uniformare il linguaggio di una squadra di redattori. Qui l'autore è uno solo e la voce è deliberatamente personale: uniformarla toglierebbe valore invece di aggiungerne |
| **`lychee`** (controllo link, anche HTTP) | **Scartato** | Il controllo dei link locali è già dentro `mdcheck.py`. Quelli HTTP richiedono rete a ogni salvataggio, sono lenti e falliscono per ragioni che non dipendono dal documento |
| **`llms.txt`** | **Scartato come standard, preso come forma** | Nato per far navigare un *sito* a un LLM: un indice curato con titolo, sintesi e link descritti. Qui non c'è un sito da esporre, ma la forma — titolo, riga di sintesi, link commentati — è esattamente quella che ho dato agli indici |
| **Riferimenti a un solo livello di profondità** | **Adottato come regola scritta** | Un file citato da un file citato da un file viene letto solo in parte (l'agente ne fa un'anteprima invece di leggerlo intero). Vale per i documenti quanto per le skill |
| **Niente informazioni che scadono** | **Adottato, e in parte meccanizzato** | Versioni, «per ora», date relative invecchiano in silenzio. La regola resta di giudizio, ma il suo *lessico* è decidibile: `mdcheck` ha un controllo opt-in (`expiring_phrases`) che segnala «per ora / oggi / currently / for now…» fuori da titoli, file o sezioni dichiarati storici o datati, più la riga «Where the project is» tenuta a mano. Su djmeta, alla prima misura: 4 segnalazioni, tutte vere |
| **Regole a percorso** (`.claude/rules/*.md` con `paths:`) | **Adottato** | Le regole Markdown erano 13 righe su 27 del `CLAUDE.md` globale, pagate in ogni sessione di ogni progetto anche senza toccare un `.md`. Ora vivono in `~/.claude/rules/markdown.md` e si caricano solo quando si tocca un `.md`; il `CLAUDE.md` globale è sceso a 9 righe. Verificato in djmeta: la rule di progetto si è caricata da sola al primo `Edit` del README |
| **Skill con template e ciclo «controlla → correggi → ripeti»** | **Adottato** | È la parte *generativa* che mancava: `~/.claude/skills/writing-docs/` con due template (documento, referto) e la checklist delle otto domande. Si carica solo quando serve, come vuole la guida sulle skill |
| **Commenti HTML scartati dal contesto** | **Adottato** | Un blocco `<!-- … -->` in `CLAUDE.md` viene tolto prima dell'iniezione: è il posto giusto per la storia che serve all'umano e costa contesto al modello. La dieta di djmeta li usa per dodici parentesi storiche |
| **`/doctor`** per potare `CLAUDE.md` | **Adottato come passo della skill** | Ufficiale: propone i tagli su ciò che il modello ricava dal codice, migra in skill ciò che resta e chiede conferma prima di toccare. Seconda opinione dopo la dieta, non sostituto: non misura e non sa quali regole devono restare |
| **Hook `type: prompt` per la metà di giudizio** | **Scartato dopo un tentativo misurato** | Aggiunto con `matcher: Write` e `if: "Write(**/*.md)"`: è scattato sulla scrittura di un `.py`, cioè `if` non filtra, e il modello veloce ha risposto in prosa invece che `{}`; quella prosa ha *bloccato il turno* invece di aggiungere contesto. Il giudizio resta dove può stare — la regola a percorso, la checklist della skill, il controllo lessicale — e nel modello principale, che ha davanti il file intero |
| **Regola dei due colpi** (una regola solo dopo lo stesso errore due volte) | **Adottato come già in uso** | È la prassi che i test-cricchetto di djmeta documentano nelle docstring: ogni controllo nasce da un errore visto, non immaginato |
| **`caveman-compress`** (skill che riscrive `CLAUDE.md` e memorie in stile telegrafico, ~46 % di token in meno dichiarati) | **Adattato, non installato** | Il suo `compress.py` è un orchestratore che chiama Claude via SDK o CLI, maschera i blocchi di codice, valida la struttura e ritenta due volte; non misura i token e tiene i backup fuori dall'albero. È esattamente ciò che una sessione fa già con il proprietario davanti, e git è il backup. Ne ho preso le *regole* (via articoli e riempitivi, frasi → frammenti, intoccabili codice/percorsi/URL/numeri) e la distinzione che gli manca: telegrafico solo nei file che legge solo Claude; per sottrazione nei file che legge anche l'umano; mai nei documenti |
| **`ctxlint`** (npm, zero dipendenze, 41 regole sui file di contesto contro il codice) | **Adottato come audit manuale, non come gate** | Provato su djmeta: misura 2 769 token per `CLAUDE.md` e pesa le sezioni, trova un percorso impreciso (`djmeta/api.py` per `src/djmeta/api.py`), nota tre divieti «inviolabili» senza hook dietro. Ma prende per percorsi anche glob e frasi (`Linux/WSL2**`, `docs/Mxx_RISULTATI.md`) e cerca `package.json` in un progetto Python: come gate farebbe rumore. Un `npx` quando serve la mappa dei token; è nella skill come passo opzionale |
| **`AgentLint`, `AgentLinter`** (npm, punteggi 0–100 sui file di contesto) | **Scartati** | Sovrapposti a `ctxlint` sui controlli che contano; il primo da `npx` espone solo `init|install`, il secondo è orientato a punteggi e report web. Un voto non dice quale riga togliere |
| **`LLMLingua`** (compressione dei prompt con un modello piccolo, fino a 20×) | **Scartato** | Fatto per comprimere prompt *al volo* prima dell'inferenza: butta token per perplessità, il risultato non è leggibile né mantenibile. I file di contesto sono sorgente, non payload |
| **Auto Dream / `/dream`** (consolidazione delle memorie) | **Scartato come dipendenza** | La comunità la descrive come funzione di Claude Code, ma la pagina ufficiale dei comandi non la elenca. Ciò che promette — date assolute, contraddizioni risolte, indice sotto le 200 righe — è già nella skill `compressing-context` e nella regola «verifica la memoria prima di comprimerla» |
| **`ctxbudget.py`** (misura del contesto sempre caricato) | **Scritto** | Nessuno strumento trovato risponde alla domanda «cosa pago a ogni avvio, file per file»: `ctxlint` conta solo i file di progetto, `/context` vive dentro una sessione. Stdlib, stima in caratteri/4 dichiarata come stima, `--max-tokens` per farne un cricchetto |

## La dieta sistematica: cosa fa da solo, e cosa no

Una dieta è sicura quando due numeri la incorniciano: *quanto pesava* e *quali
regole doveva contenere*. Il primo lo dà `ctxbudget.py`; il secondo lo dà un
test-manifesto — in djmeta `test_the_constitution_kept_every_rule`,
cinquantacinque frasi letterali che `CLAUDE.md` deve contenere — scritto
**prima** di tagliare. Fra i due, la skill `compressing-context` applica le
regole di caveman dove la forma telegrafica non costa nulla (i file che legge
solo Claude) e procede per sottrazione dove il file lo legge anche il
proprietario. Su djmeta la prima dieta, misurata con `ctxbudget.py` prima e
dopo, è passata da 199 a 183 righe pagate (197 fisiche: quattordici sono
commenti HTML che il modello non riceve) e da 11 075 a 10 164 caratteri, cioè
da ~2 769 a ~2 541 token stimati, con le cinquantacinque frasi intatte.

Cosa nessuno strumento fa: decidere che una riga *serve*. Il criterio resta
quello ufficiale — «se la tolgo, Claude sbaglia?» — e la risposta arriva dalla
sessione successiva, non da un linter.

## Le due metà, e perché la distinzione è la cosa più importante

Nessuna delle tecniche sopra tocca per intero la metà che conta di più.

- **Metà meccanica** — il documento non è *rotto*. Decidibile da uno script,
  sempre. È quello che fa l'hook.
- **Metà di giudizio** — il documento è *buono*: la risposta è in cima, la
  densità è giusta, l'indice risponde davvero, l'ordine è quello utile, **e il
  contenuto è ancora vero**. Nessuno script ci arriva: un link che risolve può
  portare a una pagina superata, e un numero scritto può essere stato vero un
  mese fa. Il controllo lessicale sulle frasi che scadono è un'approssimazione
  dichiarata, ed è SOFT per questo.

Il riordino di `MILESTONES.md` sta interamente nella seconda metà. Nessun hook
l'avrebbe prodotto, e nessun linter l'avrebbe segnalato. Per questo la metà di
giudizio vive in una regola e in una skill come policy e non come controllo:
**un run pulito significa che il pavimento tiene, non che il documento è buono.**

## Fonti

- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
  — Anthropic. Soglia delle 500 righe per SKILL.md, indice oltre le ~100 righe,
  riferimenti a un solo livello, niente informazioni che scadono, ciclo
  «validator → fix → repeat», template.
- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)
  — il limite consigliato per `CLAUDE.md`, la tabella «includi / escludi», il
  criterio «se la tolgo, Claude sbaglia?».
- [How Claude remembers your project](https://code.claude.com/docs/en/memory)
  — regole a percorso, commenti HTML scartati, import `@`, auto-memory e i suoi
  limiti (200 righe / 25 KB dell'indice), `/doctor`.
- [Commands](https://code.claude.com/docs/en/commands) — la descrizione
  ufficiale di `/doctor`: taglia il derivabile, migra in skill, chiede conferma.
- [Hooks reference](https://code.claude.com/docs/en/hooks) — Claude Code. Eventi,
  matcher, tipi `command`/`prompt`/`agent`, formato dell'output.
- [Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
  — HumanLayer. «Never send an LLM to do a linter's job»; puntatori, non copie.
- [CLAUDE.md and AGENTS.md, in depth](https://redreamality.com/blog/claude-md-agents-md-deep-dive/)
  — la regola dei due colpi, il ~70 % di adesione alle regole di solo testo,
  la separazione fra ciò che scrive l'umano e ciò che scrive l'agente.
- [Stop bloating your CLAUDE.md](https://alexop.dev/posts/stop-bloating-your-claude-md-progressive-disclosure-ai-coding-tools/)
  — alexop. La riga «leggi prima i documenti pertinenti» e una skill che
  propone aggiornamenti ai documenti a fine sessione.
- [caveman](https://github.com/JuliusBrussee/caveman) — JuliusBrussee; la skill
  `caveman-compress` e il suo `compress.py`.
- [ctxlint](https://github.com/YawLabs/ctxlint) — YawLabs, MIT;
  [AgentLint](https://github.com/0xmariowu/AgentLint) e
  [AgentLinter](https://github.com/seojoonkim/agentlinter) — i concorrenti.
- [LLMLingua](https://github.com/microsoft/LLMLingua) — Microsoft Research.
- [markdownlint — RULES.md](https://github.com/markdownlint/markdownlint/blob/main/docs/RULES.md)
  — MD024 e la sua opzione `siblings_only`, MD051.
- [PyMarkdown Linter](https://pymarkdown.readthedocs.io/) — l'alternativa pura
  Python a markdownlint.
- [Vale](https://docsio.co/blog/vale-linter) e
  [guida al linting della documentazione](https://buildwithfern.com/post/docs-linting-guide)
  — il panorama docs-as-code.
- [Il file /llms.txt](https://llmstxt.org/) — Jeremy Howard, 2024.

## Storico

- **2026-09-07** — prima stesura: mdcheck con U1–U4 e C1, le cinque regole nel
  `CLAUDE.md` globale.
- **2026-09-07**, seconda passata — le regole spostate in
  `~/.claude/rules/markdown.md`; nasce la skill `writing-docs`; mdcheck guadagna
  `expiring_phrases` (C2, C3); l'hook `prompt` provato e tolto lo stesso giorno.
- **2026-09-07**, terza passata — la ricerca sulla dieta: `ctxbudget.py`, la
  skill `compressing-context`, il test-manifesto; `~/.claude/tools` pubblicato
  su GitHub (`mirkomustari/claude-tools`, MIT, `v0.1.0`) per il pre-commit e la
  CI di djmeta.
