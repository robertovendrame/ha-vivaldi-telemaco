# Vivaldi Telemaco per Home Assistant

Integrazione custom HACS per il sistema audio multiroom **Vivaldi Telemaco**.

La versione 0.3 implementa i topic ufficiali **TELEMACO MQTT API 1.1** e la
specifica completa **Telemaco RestAPI 1.2.0**.

## Funzioni

- Configurazione interamente da interfaccia grafica.
- Rilevamento locale mDNS/zeroconf.
- REST locale JSON con access token.
- MQTT tramite il broker già configurato in Home Assistant.
- Modalità `API`, `MQTT` o `ibrida`.
- Un'entità `media_player` per ciascuna delle 6/12 zone.
- Un'entità `media_player` per ciascuno dei 4/6 player indipendenti.
- Volume e mute zona, matrice player/zone, play, pausa, stop, traccia
  precedente/successiva.
- Titolo, artista, album, copertina, shuffle, repeat e preset attivo.
- Equalizzatore bassi, medi e alti da -10 a +10 dB per uscita.
- Rilevamento del segnale sui canali.
- Modalità SINGLE, MULTI e SLAVE e disponibilità aggiornamenti.
- Sensori di errore per i sei/dodici amplificatori.
- Versione firmware, diagnostica anonimizzata e aggiornamento manuale.
- Servizi per preset, campanello e comandi JSON avanzati.
- Gestione di due Telemaco accoppiati.

## Installazione manuale

1. Copiare `custom_components/vivaldi_telemaco` in
   `/config/custom_components/vivaldi_telemaco`.
2. Riavviare Home Assistant.
3. Aprire **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**.
4. Cercare **Vivaldi Telemaco**.

## Installazione come repository HACS personalizzato

Pubblicare questa cartella in un repository GitHub, quindi in HACS scegliere:

1. **Integrazioni → menu ⋮ → Repository personalizzati**.
2. Incollare l'URL del repository.
3. Categoria: **Integrazione**.

## Parametri

| Campo | Uso |
|---|---|
| Host | IP statico o nome mDNS del Telemaco |
| Porta | Normalmente 80; 443 per HTTPS |
| Trasporto | API, MQTT oppure ibrido |
| Utente/password | Credenziali della webpage; il JWT viene gestito automaticamente |
| Token API | Alternativa avanzata alle credenziali |
| Prefisso MQTT | `root_topic` dell'annuncio, ad esempio `vivaldi/telemaco_86919e` |
| Zone | 6 con un dispositivo, 12 con due dispositivi accoppiati |
| Player | 4 con un dispositivo; fino a 6 con due dispositivi |

La modalità ibrida usa gli eventi MQTT per aggiornamenti immediati e REST come
controllo periodico/fallback.

## Servizi

### `vivaldi_telemaco.play_preset`

```yaml
action: vivaldi_telemaco.play_preset
data:
  player: 1
  preset: 3
```

### `vivaldi_telemaco.doorbell`

```yaml
action: vivaldi_telemaco.doorbell
data:
  sound: 0
```

### `vivaldi_telemaco.send_command`

Servizio per sviluppo e funzioni non ancora modellate. Richiede un comando e
un oggetto JSON. Usarlo solo conoscendo il payload previsto dal firmware.

## Supporto REST

L'integrazione effettua login con username/password, conserva il JWT solo nella
memoria di Home Assistant, lo rinnova prima della scadenza e ripete il login in
caso di risposta 401. Sono modellate le risorse device, metadata, preset,
input, matrix, output, nomi, multiroom e stato API.

Lo script `tools/capture_rest.py` esegue esclusivamente richieste GET sugli
endpoint di stato e sui percorsi tipici OpenAPI, oscurando i campi sensibili:

```bash
python3 tools/capture_rest.py 192.168.1.180 --token "TOKEN"
```

La normalizzazione è isolata in `protocol.py`; endpoint, topic e nomi dei
comandi possono quindi essere aggiornati senza riscrivere le entità.

## Sicurezza

- Il token non viene scritto nei log o nella diagnostica.
- Il rilevamento REST prova solo richieste `GET`.
- Nessun endpoint di reset, rete o aggiornamento firmware è esposto.
- MQTT usa il broker di Home Assistant e non conserva credenziali proprie.

## Licenza

MIT. “Vivaldi” e “Telemaco” appartengono ai rispettivi titolari.
