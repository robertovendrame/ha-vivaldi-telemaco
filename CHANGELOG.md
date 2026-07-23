# Changelog

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
