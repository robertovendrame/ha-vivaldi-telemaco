# Changelog

## 0.4.3

- Aggiunge la connessione diretta al broker MQTT interno del Telemaco quando
  Home Assistant MQTT non è configurato.
- Riceve il volume reale delle zone anche dopo un riavvio di Home Assistant.
- Aggiunge broker, porta e prefisso MQTT alle opzioni dell'integrazione.

## 0.4.2

- Aggiunge regolazione volume 0-100% e mute/unmute per ogni player.
- Supporta i comandi player volume e mute sia tramite REST sia tramite MQTT.
- Aggiorna immediatamente lo stato Home Assistant dopo ogni comando.

## 0.4.1

- Aggiunge lo spegnimento nativo delle zone, scollegandole da tutti i player.
- Aggiunge `Nessuna` al selettore sorgente come alternativa allo spegnimento.
- Rinomina il comando DND in `Escludi campanello` per chiarirne la funzione.

## 0.4.0

- Aggiunge il supporto locale ai moduli Vivaldi C4IO tramite WebSocket.
- Crea quattro entità evento per ogni C4IO con `short_press` e `long_press`,
  indipendenti dalle associazioni configurate sul modulo.
- Aggiunge stato di connessione e sensori diagnostici firmware/RSSI.
- Gestisce automaticamente disconnessioni e riconnessioni dei C4IO.

## 0.3.5

- Legge `volume`, `mute` e `dnd` quando il firmware li espone in
  `/api/output/get`.
- In modalità solo REST conserva e aggiorna immediatamente l'ultimo volume
  noto, evitando che il controllo torni a 0% dopo ogni polling.
- Mostra i nomi configurati dei player nel selettore sorgente delle zone.

## 0.3.4

- Correzione della collisione tra il modulo MQTT di Home Assistant e il modulo
  MQTT interno dell'integrazione.

## 0.3.3

- Attesa corretta del client MQTT di Home Assistant prima della sottoscrizione.
- Fallback automatico a REST per le configurazioni ibride senza MQTT.
- Errore riprovabile e comprensibile per le configurazioni solo MQTT prive di
  un'integrazione MQTT configurata.

## 0.3.2

- Correzione dei comandi MQTT: volume, mute e controlli player non leggono più
  parametri appartenenti ad altri comandi.
- Eliminato il `KeyError: 'shuffle'` durante la regolazione del volume.

## 0.3.1

- Rimossa la dichiarazione Zeroconf incompleta che impediva l'avvio del
  componente Zeroconf di Home Assistant.

## 0.3.0

- Implementazione della specifica Telemaco RestAPI 1.2.0 completa.
- Login automatico con credenziali della webpage.
- Gestione JWT, scadenza, refresh e riautenticazione.
- Normalizzazione delle risorse Metadata, Presets, Input, Matrix, Output,
  Hostnames, Device, API e Multiroom.
- Matrice player/zone via REST.
- Correzione identificatori REST `player1` e `ch1`.
- Test dedicati ai payload REST ufficiali.

## 0.2.0

- Implementazione TELEMACO MQTT API 1.1.
- Topic stato scalari e comandi `set` ufficiali.
- Matrice player/zone mono.
- Metadati player, copertina, shuffle, repeat e preset.
- EQ a tre bande e rilevamento segnale.
- Stato SINGLE/MULTI/SLAVE e aggiornamento disponibile.
- Endpoint REST 1.2.0 visibili nella documentazione Swagger.
- Player REST, preset, uscite mono, DND e campanello.
- Lettura aggregata delle risorse REST.

## 0.1.0

- Prima ossatura HACS con config flow, entità e diagnostica.
