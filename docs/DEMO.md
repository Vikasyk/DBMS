# TraceFood lab demonstration

Use a fresh demo database for the recording workflow. The numbered batch IDs below belong to the standard fixture unless they are given as variables for newly created records. The write steps can be repeated with fresh IDs and create additional history.

## Trace a recorded case

1. Show the Chen ER and relational diagrams. Point out the two foreign keys from `batch_derivation` to `batch`, and explain why input quantity belongs to that relationship.
2. On **Batch trace**, select `B101`. Follow the arrows to `B103` and then `B105`. In the stored fixture, `B101` starts at 100 kg and has 40 kg available.
3. Under **Quality checks**, open `QC4` from **Investigations**. Show the confirmed failed check on `B103`, possible sources `B101` and `B102`, and potentially affected `B105`. The last recorded pass is `QC3`. The possible window runs from 9 to 14 January 2026.
4. In **What-if simulation**, enter `B101`. The simulated distribution reaches `R01`, `R02`, and `R03`. Verify that `SELECT count(*) FROM tracefood.quality_check` returns the same value before and after the simulation.

## Record a supply chain

1. In **Register**, create two original Tomato batches from `F01` and `F02`, with 100 kg and 50 kg. Use 1 June 2026 as their production date. Try a negative quantity in the registration form or interactive API and show the rejection.
2. In **Processing**, take 40 kg and 20 kg from the two batches to create 54 kg of Tomato Puree at `PF01`. Use the next day and a valid expiry date. Record the new batch ID and show its lineage.
3. Try another operation using 70 kg from the first input, which has only 60 kg available. Show the rejection. Repeat with **Allow over-allocation** enabled. The SQL rule can review the resulting stock discrepancy.
4. In **Shipments**, send 15 kg of puree and 5 kg of the second input to `R01`. Show the recorded item rows and the 20 kg shipment total. Each unit receives its own total.
5. Under **Quality checks**, record a FAIL for the new puree batch after shipping. Open its real investigation report and compare it with the hypothetical report.
6. Under **Prices and forecasts**, add an observation for a batch that was produced on or before the price date. View Tomato in **Stage comparison**, then show historical movements. Retail price changes and recorded unit costs do not establish profit.

## Review anomalies and ask a question

1. In **Anomalies**, run the detectors. On an untouched fixture the SQL rules produce three alerts. The additional processing step produces an over-allocation alert. Open `B107`'s mass-balance alert and show the 80 kg input and 95 kg output behind the score. Mark the reviewed alert through the UI.
2. In **Ask TraceFood**, ask “Which retailers received products derived from B101?” Inspect the returned rows and the SQL template with the bound batch ID. Enter “Delete all alerts” and check that no query is run.
3. In the demo database, try **Forecast** for Tomato, Bengaluru, kg. The fixture has too few consecutive weeks. Repeat with the synthetic database to see the measured methods, the chosen model, and four forecast weeks.
4. Run `db/tests/regression.sql` to show which objects the natural-language reader can access, how PostgreSQL denies writes, and how the timeout works.
5. Run the downstream index comparison on the isolated synthetic database. Compare matching result counts, PostgreSQL plans, and median planning and execution times. Open the measured values in [the data notes](../data/README.md).
