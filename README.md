# Energietracker for Home Assistant

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Bingerminger&repository=energietracker-integration&category=integration)

**English** · [Deutsch](#deutsch)

**Energietracker sensors in Home Assistant, without YAML.** To do, next
appointment, balance per meter with the expected and the measured balance,
consumption this year, 12-month forecast and days since the last reading.
Needs Energietracker 3.9.0 or later and Home Assistant 2026.3 or later.

[Energietracker](https://github.com/Bingerminger/energietracker) is the
self-hosted energy cockpit for your home; this custom integration reads it.

## Requirements

- Energietracker **3.9.0** or later. The attributes for the expected and the
  measured balance, “due soon” and the next appointment need **3.10.0**; with
  3.9 they stay empty.
- Home Assistant **2026.3** or later.

## Installation

Until the integration is in the HACS default list, you add it as a **custom
repository**. The button above opens it directly.

**Home Assistant 2026.11 or later: in the Marketplace.** Since 2026.11, HACS is
built into Home Assistant as the **Marketplace**.

1. **Connect the Marketplace to GitHub once.** It shows a code that you enter at
   `https://github.com/login/device`. The connection only reads public
   information; the Marketplace needs it for custom repositories.
2. Add the custom repository
   `https://github.com/Bingerminger/energietracker-integration`, type **Integration**.
3. Open **Energietracker**, **Download**, then restart Home Assistant.
4. **Settings → Devices & services → Add integration → Energietracker**.

**Home Assistant 2026.3 to 2026.10: with HACS.**

1. HACS → menu **⋮ → Custom repositories**, add
   `https://github.com/Bingerminger/energietracker-integration`, type **Integration**.
2. Open **Energietracker** in HACS, **Download**, then restart Home Assistant.
3. **Settings → Devices & services → Add integration → Energietracker**.

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

A group of meters with a group contract (for example a heat pump with two
tariff meters) gets a device of its own with **Balance** only; its members
have none. A sum over all balance sensors counts every contract once.

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
  deliveries are recorded.

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
the integration in HACS (or delete the folder
`custom_components/energietracker`) and restart Home Assistant.

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
Jahresbeginn, Prognose 12 Monate und Tage seit der letzten Ablesung. Braucht
den Energietracker 3.9.0 oder neuer und Home Assistant 2026.3 oder neuer.

Der [Energietracker](https://github.com/Bingerminger/energietracker) ist das
selbst gehostete Energie-Cockpit für dein Zuhause; diese Integration liest ihn
aus.

### Voraussetzungen

- Energietracker **3.9.0** oder neuer. Die Attribute für den erwarteten und
  den gemessenen Saldo, „bald fällig“ und den nächsten Termin brauchen
  **3.10.0**; mit 3.9 bleiben sie leer.
- Home Assistant **2026.3** oder neuer.

### Installation

Bis die Integration in der Standardliste von HACS steht, fügst du sie als
**benutzerdefiniertes Repository** hinzu. Der Knopf oben öffnet sie direkt.

**Home Assistant ab 2026.11: im Marketplace.** Seit 2026.11 ist HACS als
**Marketplace** fest in Home Assistant eingebaut.

1. **Den Marketplace einmal mit GitHub verbinden.** Er zeigt einen Code, den du
   unter `https://github.com/login/device` eingibst. Die Verbindung liest nur
   Öffentliches; der Marketplace braucht sie für benutzerdefinierte Repositories.
2. Das benutzerdefinierte Repository
   `https://github.com/Bingerminger/energietracker-integration` hinzufügen, Typ
   **Integration**.
3. **Energietracker** öffnen, **Herunterladen**, dann Home Assistant neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Energietracker**.

**Home Assistant 2026.3 bis 2026.10: mit HACS.**

1. HACS → Menü **⋮ → Benutzerdefinierte Repositories**,
   `https://github.com/Bingerminger/energietracker-integration` eintragen, Typ
   **Integration**.
2. **Energietracker** in HACS öffnen, **Herunterladen**, dann Home Assistant
   neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Energietracker**.

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

Eine Zählergruppe mit Gruppenvertrag (etwa eine Wärmepumpe mit zwei
Tarifzählern) bekommt ein eigenes Gerät nur mit **Saldo**; ihre Mitglieder
haben keinen. Wer über alle Saldo-Sensoren summiert, zählt jeden Vertrag
einmal.

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
  Lieferungen erfasst sind.

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
die Integration in HACS entfernen (oder den Ordner
`custom_components/energietracker` löschen) und Home Assistant neu starten.

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
