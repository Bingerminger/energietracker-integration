# Energietracker for Home Assistant

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=Bingerminger&repository=energietracker-integration&category=integration)
[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Bingerminger&repository=energietracker-integration&category=integration)

**English** · [Deutsch](#deutsch)

**Energietracker sensors in Home Assistant, without YAML.** To do, next
appointment, balance per meter with the expected and the measured balance,
consumption this year, 12-month forecast and days since the last reading;
stock and fill level of oil and pellet tanks, the forecast of a group contract
and the payouts of the feed-in.
Needs Energietracker 3.9.0 or later and Home Assistant 2026.3 or later.

[Energietracker](https://github.com/Bingerminger/energietracker) is the
self-hosted energy cockpit for your home; this custom integration reads it.

## Requirements

- Energietracker **3.9.0** or later. The attributes for the expected and the
  measured balance, “due soon” and the next appointment need **3.10.0**; with
  3.9 they stay empty. Stock and fill level of a tank, the forecast of a group
  contract and the payouts of the feed-in need **3.13.0**: the sensors appear
  once Energietracker has the update and the integration is reloaded
  (**Settings → Devices & services → Energietracker → ⋮ → Reload**).
- Home Assistant **2026.3** or later.

## Installation

**Search for “Energietracker” in the Marketplace (formerly HACS).** The
integration is in the default list of the Marketplace. The buttons above open
it directly: the first in the Marketplace, the second in HACS.

1. Marketplace → search for **Energietracker** → **Download**, then restart
   Home Assistant.
2. **Settings → Devices & services → Add integration → Energietracker**.

**Home Assistant 2026.3 to 2026.10:** use HACS instead and search the
same way (HACS → search for **Energietracker** → **Download**).

**By hand:** copy the folder `custom_components/energietracker` of the
[latest release](https://github.com/Bingerminger/energietracker-integration/releases/latest)
into the folder `custom_components` of your Home Assistant configuration and
restart Home Assistant.

## Setup

| Field | What to enter |
|---|---|
| Address | where you open Energietracker, for example `http://nas.local:8080` or `http://nas.local/energietracker`. For the Energietracker app in Home Assistant, Energietracker shows the address under **Connections → Home Assistant** (up to 3.11: Settings → Integrations). |
| Read key | only when sign-in is switched on in Energietracker: **Connections → Keys → API keys for scripts**, scope **Read** (`etk_…`; up to 3.11 under Settings → Access). A pasted `Bearer ` is removed. |
| Verify the certificate | switch it off only for `https://` with a certificate of your own. |

The integration asks every 15 minutes. One entry per Energietracker
installation; it is recognised by its `instance_id`, so a second entry for the
same installation is refused.

## Sensors

Device **Energietracker** (one per installation):

| Sensor | Value | Attributes |
|---|---|---|
| To do | number of due items | `overdue` (overdue or urgent), `soon` (appointments due within the lead time of “due soon” in Energietracker), `next_upcoming` (the next appointment), `items` (up to 20, each `title`, `date`, `kind`, `severity`) |
| Next item | title of the next due item (overdue first, then urgent, then by date) | `date`, `kind`, `severity` |
| Next item due | its date | |
| Next appointment | title of the next appointment that is not due yet, however far away | `date`, `kind`, `severity` |
| Next appointment on | its date | |

One device per meter, named after the kind of energy and the meter
(“Electricity main meter”):

| Sensor | Meters | Value |
|---|---|---|
| Balance | with a current contract | balance up to today, in the currency of the installation |
| Consumption this year | all | since 1 January, in kWh or m³ |
| Forecast 12 months | all except heating oil and pellets | in kWh or m³ |
| Days since reading | all | days |
| Stock | heating oil and pellets (3.13.0) | what is in the tank today, in the unit of the tank (L or kg); attributes `capacity` (in the same unit) and `estimated_from` (the last day with a known stock: initial stock, a delivery “filled up” or a tank reading; from then on the stock is estimated) |
| Fill level | heating oil and pellets (3.13.0) | stock as a share of the capacity, in % |
| Already paid out | feed-in with a current contract (3.13.0) | what the grid operator has paid out for the billing year, as recorded at the balance card |
| Still outstanding | feed-in with a current contract (3.13.0) | balance up to today minus what has been paid out |
| Outstanding at settlement | feed-in with a current contract (3.13.0) | expected balance at settlement minus what has been paid out |

A group of meters with a group contract (for example a heat pump with two
tariff meters) gets a device of its own with **Balance**; its members have
none. A sum over all balance sensors counts every contract once. With
Energietracker 3.13.0 the group also gets:

| Sensor | Value |
|---|---|
| Forecast 12 months | the next 12 months of the group (peak plus off-peak), in kWh |
| Forecast costs 12 months | their costs under the group contract, each register at its own price, with the standing charge, in the currency of the installation |

The members keep their own **Forecast 12 months**; a sum over the members
and the group would count the group twice.

### Payouts of the feed-in

For the feed-in, **Balance** stays the claim for the billing year (positive =
the grid operator owes you). The three payout sensors split it up: **Already
paid out** is the sum of the payouts recorded in Energietracker for the
billing year (0 until the first one), **Still outstanding** and
**Outstanding at settlement** are what is left of the claim today and at
settlement.

### Balance

The sign is Energietracker’s: positive = back-payment (for feed-in: payout),
negative = refund. The **state** is the balance up to today, estimated for
the days since the last reading, like “Estimated up to today” on the balance
card. The attributes add what the card shows:

| Attribute | Meaning |
|---|---|
| `projected_end_balance_total` | “Expected at settlement”: the expected balance of the next bill; when one bill settles several contracts (a tariff change with the same supplier), their sum |
| `projected_end_range_total` | `[low, high]` when the estimate is uncertain; the card then shows only this range, and the value above is a single point of it |
| `projected_end_balance` | the expected balance of the current contract alone |
| `measured_balance` | the balance up to the last reading, without estimate (“Balance on …”) |
| `measured_until` | the day of that reading |

In a template: `{{ state_attr('sensor.electricity_main_meter_balance', 'projected_end_balance_total') }}`
(check the entity id under Settings → Devices & services → Entities).

### Good to know

- The meter sensors are evaluations, not meter readings, so they have no
  state class. For the energy dashboard use the meters of Home Assistant
  itself.
- A new meter in Energietracker appears after reloading the integration. A
  meter deleted in Energietracker can then be deleted on its device page.
- Every new kind of item in Energietracker’s “To do” list counts without an
  update of this integration.
- Heating oil and pellets: “Days since reading” stays unknown while only
  deliveries are recorded. **Stock** and **Fill level** come from
  Energietracker’s tank book: after the last delivery “filled up” or tank
  reading, the stock is estimated from the consumption so far and the heating
  degree days.

## When something is wrong

| What you see | Why, and what to do |
|---|---|
| “Re-authentication required” | sign-in was switched on in Energietracker, or the read key was revoked. Enter a key with scope **Read**. |
| Repair notice “Energietracker is too old” | the installation runs a version before 3.9.0. Update Energietracker; the integration retries by itself and the notice goes away. |
| Sensors “unavailable” | Energietracker cannot be reached. The integration asks again at the next update. |
| Setup: “The answer does not come from Energietracker” | the address leads to another service, or the path is missing (`/energietracker`). |

## Notifications

Due appointments, deadlines, warnings and new documents are reported by
Energietracker itself (**Connections → Notifications**; up to 3.11 under
Settings → Integrations); that needs no integration. See the
[handbook, step 6](https://github.com/Bingerminger/energietracker/blob/main/docs/en/anleitungen/home-assistant.md#step-6--notifications-to-home-assistant-v390).

## Removal

**Settings → Devices & services → Energietracker → ⋮ → Delete**, then remove
the integration in the Marketplace (up to Home Assistant 2026.10: in HACS), or
delete the folder `custom_components/energietracker`, and restart Home
Assistant.

## Questions and bugs

**Bugs and questions about the integration go to the
[issues](https://github.com/Bingerminger/energietracker-integration/issues) here;**
ideas for Energietracker itself to the
[Discussions](https://github.com/Bingerminger/energietracker/discussions) of the
main project.

## Privacy

The integration only talks to the address you enter. Nothing leaves your home
network unless that address lies outside it. The read key stays in Home
Assistant.

## Versions

The integration counts its own versions (SemVer, from 1.0.0). It reads only
the stable interfaces `GET /api/summary` and `GET /api/todo` of Energietracker,
which only grow: a new Energietracker release needs no new integration
release.

## Development

The logic without Home Assistant (`logic.py`) and the repository checks
(translations, manifest, brand images) need only the standard library:

```bash
python3 -I -m unittest discover -s tests
```

## License

GNU Affero General Public License v3.0 or later, like Energietracker itself
([LICENSE](LICENSE)).

---

## Deutsch

**Energietracker-Sensoren in Home Assistant, ohne YAML.** Zu tun, nächster
Termin, Saldo je Zähler mit erwartetem und gemessenem Saldo, Verbrauch seit
Jahresbeginn, Prognose 12 Monate und Tage seit der letzten Ablesung; Bestand
und Füllstand von Öl- und Pellettanks, die Prognose eines Gruppenvertrags und
die Auszahlungen der Einspeisung. Braucht den Energietracker 3.9.0 oder neuer
und Home Assistant 2026.3 oder neuer.

Der [Energietracker](https://github.com/Bingerminger/energietracker) ist das
selbst gehostete Energie-Cockpit für dein Zuhause; diese Integration liest ihn
aus.

### Voraussetzungen

- Energietracker **3.9.0** oder neuer. Die Attribute für den erwarteten und
  den gemessenen Saldo, „bald fällig“ und den nächsten Termin brauchen
  **3.10.0**; mit 3.9 bleiben sie leer. Bestand und Füllstand eines Tanks, die
  Prognose eines Gruppenvertrags und die Auszahlungen der Einspeisung brauchen
  **3.13.0**: Die Sensoren erscheinen, sobald der Energietracker das Update hat
  und die Integration neu geladen ist (**Einstellungen → Geräte & Dienste →
  Energietracker → ⋮ → Neu laden**).
- Home Assistant **2026.3** oder neuer.

### Installation

**Im Marketplace (ehemals HACS) nach „Energietracker“ suchen.** Die
Integration steht in der Standardliste des Marketplace. Die Knöpfe oben öffnen
sie direkt: der erste im Marketplace, der zweite in HACS.

1. Marketplace → nach **Energietracker** suchen → **Herunterladen**, dann Home
   Assistant neu starten.
2. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Energietracker**.

**Home Assistant 2026.3 bis 2026.10:** Dort heißt der Weg HACS, ebenfalls über
die Suche (HACS → nach **Energietracker** suchen → **Herunterladen**).

**Von Hand:** den Ordner `custom_components/energietracker` aus dem
[neuesten Release](https://github.com/Bingerminger/energietracker-integration/releases/latest)
in den Ordner `custom_components` deiner Home-Assistant-Konfiguration kopieren
und Home Assistant neu starten.

### Einrichtung

| Feld | Was du einträgst |
|---|---|
| Adresse | wo du den Energietracker öffnest, etwa `http://nas.local:8080` oder `http://nas.local/energietracker`. Bei der App in Home Assistant zeigt der Energietracker die Adresse unter **Verbindungen → Home Assistant** (bis 3.11: Einstellungen → Integrationen). |
| Lese-Schlüssel | nur, wenn im Energietracker die Anmeldung eingeschaltet ist: **Verbindungen → Schlüssel → API-Schlüssel für Skripte**, Bereich **Lesen** (`etk_…`; bis 3.11 unter Einstellungen → Zugriff). Ein mitkopiertes `Bearer ` fällt weg. |
| Zertifikat prüfen | nur bei `https://` mit eigenem Zertifikat ausschalten. |

Die Integration fragt alle 15 Minuten. Ein Eintrag je Installation des
Energietrackers; erkannt wird sie an ihrer `instance_id`, ein zweiter Eintrag
für dieselbe Installation wird abgelehnt.

### Sensoren

Gerät **Energietracker** (eines je Installation):

| Sensor | Wert | Attribute |
|---|---|---|
| Zu tun | Zahl der fälligen Punkte | `overdue` (überfällig oder dringend), `soon` (Termine, die im Vorlauf von „bald fällig“ im Energietracker fällig werden), `next_upcoming` (der nächste Termin), `items` (bis zu 20, je `title`, `date`, `kind`, `severity`) |
| Nächster Punkt | Titel des nächsten fälligen Punkts (überfällig zuerst, dann dringend, dann nach Datum) | `date`, `kind`, `severity` |
| Nächster Punkt fällig | sein Datum | |
| Nächster Termin | Titel des nächsten Termins, der noch nicht fällig ist, auch wenn er weit weg liegt | `date`, `kind`, `severity` |
| Nächster Termin am | sein Datum | |

Ein Gerät je Zähler, benannt nach Verbrauchsart und Zähler („Strom
Hauptzähler“):

| Sensor | Zähler | Wert |
|---|---|---|
| Saldo | mit laufendem Vertrag | Saldo bis heute, in der Währung der Installation |
| Verbrauch seit Jahresbeginn | alle | seit dem 1. Januar, in kWh oder m³ |
| Prognose 12 Monate | alle außer Heizöl und Pellets | in kWh oder m³ |
| Tage seit Ablesung | alle | Tage |
| Bestand | Heizöl und Pellets (3.13.0) | was heute im Tank ist, in der Einheit des Tanks (L oder kg); Attribute `capacity` (in derselben Einheit) und `estimated_from` (der letzte Tag mit bekanntem Bestand: Anfangsbestand, Lieferung „bis voll“ oder Peilstand; ab da ist der Bestand geschätzt) |
| Füllstand | Heizöl und Pellets (3.13.0) | Bestand als Anteil der Kapazität, in % |
| Bereits ausgezahlt | Einspeisung mit laufendem Vertrag (3.13.0) | was der Netzbetreiber für das Abrechnungsjahr ausgezahlt hat, wie an der Saldo-Karte erfasst |
| Noch offen | Einspeisung mit laufendem Vertrag (3.13.0) | Saldo bis heute abzüglich der Auszahlungen |
| Offen bei Abrechnung | Einspeisung mit laufendem Vertrag (3.13.0) | erwarteter Saldo bei Abrechnung abzüglich der Auszahlungen |

Eine Zählergruppe mit Gruppenvertrag (etwa eine Wärmepumpe mit zwei
Tarifzählern) bekommt ein eigenes Gerät mit **Saldo**; ihre Mitglieder haben
keinen. Wer über alle Saldo-Sensoren summiert, zählt jeden Vertrag einmal. Mit
dem Energietracker 3.13.0 bekommt die Gruppe dazu:

| Sensor | Wert |
|---|---|
| Prognose 12 Monate | die nächsten 12 Monate der Gruppe (HT plus NT), in kWh |
| Prognose Kosten 12 Monate | ihre Kosten nach dem Gruppenvertrag, jedes Zählwerk zu seinem Preis, mit Grundpreis, in der Währung der Installation |

Die Mitglieder behalten ihre eigene **Prognose 12 Monate**; wer über
Mitglieder und Gruppe summiert, zählt die Gruppe doppelt.

#### Auszahlungen der Einspeisung

Bei der Einspeisung bleibt **Saldo** der Anspruch im Abrechnungsjahr (positiv =
der Netzbetreiber schuldet dir Geld). Die drei Sensoren der Auszahlungen
teilen ihn auf: **Bereits ausgezahlt** ist die Summe der im Energietracker
erfassten Auszahlungen für das Abrechnungsjahr (0 bis zur ersten), **Noch
offen** und **Offen bei Abrechnung** sind, was vom Anspruch heute und zur
Abrechnung übrig ist.

#### Saldo

Das Vorzeichen ist das des Energietrackers: positiv = Nachzahlung (bei der
Einspeisung: Auszahlung), negativ = Guthaben. Der **Zustand** ist der Saldo
bis heute, die Tage seit der letzten Ablesung geschätzt, wie „Bis heute
geschätzt“ auf der Saldo-Karte. Die Attribute ergänzen, was die Karte zeigt:

| Attribut | Bedeutung |
|---|---|
| `projected_end_balance_total` | „Erwartet bei Abrechnung“: der erwartete Saldo der nächsten Abrechnung; rechnet eine Abrechnung mehrere Verträge ab (Tarifwechsel beim selben Versorger), ihre Summe |
| `projected_end_range_total` | `[von, bis]`, wenn die Schätzung unsicher ist; die Karte zeigt dann nur diese Spanne, der Wert darüber ist ein einzelner Punkt daraus |
| `projected_end_balance` | der erwartete Saldo nur des laufenden Vertrags |
| `measured_balance` | der Saldo bis zur letzten Ablesung, ohne Schätzung („Saldo am …“) |
| `measured_until` | der Tag dieser Ablesung |

In einer Vorlage: `{{ state_attr('sensor.strom_hauptzahler_saldo', 'projected_end_balance_total') }}`
(die Entitäts-ID unter Einstellungen → Geräte & Dienste → Entitäten prüfen).

#### Gut zu wissen

- Die Zähler-Sensoren sind Auswertungen, keine Zählerstände, deshalb ohne
  Zustandsklasse. Fürs Energie-Dashboard die Zähler aus Home Assistant selbst
  nehmen.
- Ein neuer Zähler im Energietracker erscheint nach dem Neuladen der
  Integration. Ein im Energietracker gelöschter Zähler lässt sich danach auf
  seiner Geräteseite löschen.
- Jede neue Art von Punkt in „Zu tun“ zählt mit, ohne Update der Integration.
- Heizöl und Pellets: „Tage seit Ablesung“ bleibt unbekannt, solange nur
  Lieferungen erfasst sind. **Bestand** und **Füllstand** kommen aus dem
  Tankbuch des Energietrackers: Nach der letzten Lieferung „bis voll“ oder dem
  letzten Peilstand ist der Bestand aus dem bisherigen Verbrauch und den
  Heizgradtagen geschätzt.

### Wenn etwas nicht stimmt

| Was du siehst | Warum, und was zu tun ist |
|---|---|
| „Erneute Authentifizierung erforderlich“ | im Energietracker wurde die Anmeldung eingeschaltet oder der Lese-Schlüssel widerrufen. Einen Schlüssel mit Bereich **Lesen** eintragen. |
| Reparaturhinweis „Der Energietracker ist zu alt“ | die Installation läuft mit einer Version vor 3.9.0. Den Energietracker aktualisieren; die Integration versucht es von selbst weiter, der Hinweis verschwindet. |
| Sensoren „nicht verfügbar“ | der Energietracker ist nicht erreichbar. Die Integration fragt beim nächsten Abruf wieder. |
| Einrichtung: „Die Antwort kommt nicht vom Energietracker“ | die Adresse führt zu einem anderen Dienst, oder der Pfad fehlt (`/energietracker`). |

### Benachrichtigungen

Fällige Termine, Fristen, Warnungen und neue Dokumente meldet der
Energietracker selbst (**Verbindungen → Benachrichtigungen**; bis 3.11 unter
Einstellungen → Integrationen); dafür braucht es keine Integration. Siehe
[Handbuch, Schritt 6](https://github.com/Bingerminger/energietracker/blob/main/docs/anleitungen/home-assistant.md#schritt-6--benachrichtigungen-an-home-assistant-v390).

### Entfernen

**Einstellungen → Geräte & Dienste → Energietracker → ⋮ → Löschen**, danach
die Integration im Marketplace entfernen (bis Home Assistant 2026.10 in HACS)
oder den Ordner `custom_components/energietracker` löschen und Home Assistant
neu starten.

### Fragen und Fehler

**Fehler und Fragen zur Integration gehören in die
[Issues](https://github.com/Bingerminger/energietracker-integration/issues) hier;**
Ideen für den Energietracker selbst in die
[Discussions](https://github.com/Bingerminger/energietracker/discussions) des
Hauptprojekts.

### Datenschutz

Die Integration spricht nur die Adresse an, die du einträgst. Nichts verlässt
dein Heimnetz, außer diese Adresse liegt außerhalb. Der Lese-Schlüssel bleibt
in Home Assistant.

### Versionen

Die Integration zählt eigene Versionen (SemVer, ab 1.0.0). Sie liest nur die
stabilen Schnittstellen `GET /api/summary` und `GET /api/todo` des
Energietrackers, die nur wachsen: Ein neues Release des Energietrackers braucht
kein neues Release der Integration.

### Lizenz

GNU Affero General Public License v3.0 oder neuer, wie der Energietracker
selbst ([LICENSE](LICENSE)).
