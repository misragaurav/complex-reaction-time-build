# CRT Lab — Researcher Training Guide

This guide explains, in plain language, what happens when a participant runs
a session, how reaction time (RT) is measured, and how to read the
`trials.csv` file you get from **Export study data (ZIP)**.

---

## Part 1 — What happens during a session, step by step

A "session" is one sitting where a participant completes a practice block
and a test block of the choice-reaction-time task.

1. **Participant logs in** with their participant code and password, and
   opens their session list. Sessions must be done **in order** — they can't
   skip ahead to session 2 before finishing session 1.

2. **The app checks the screen.** If the device is a phone/tablet (touch
   screen) or the browser window is too small, the participant sees a
   message telling them to use a laptop/desktop with a larger screen. Nothing
   is recorded for that attempt — they simply can't start until they switch
   devices.

3. **(If needed) Demographic questions.** If the study has demographic
   questions that are due (e.g. age, handedness — either "ask once" or "ask
   every session"), the participant answers them before the task starts.

4. **Instructions screen.** The participant is shown the task instructions
   (which keys to press for which positions, how many trials, etc.) and
   clicks to begin. The screen goes full-screen at this point.

5. **Practice block.** A short set of practice trials runs (the number is
   set in the study's parameters). Each trial looks like this:
   - **Wait (ITI – "inter-trial interval").** The screen shows resting
     crosses for a brief, fixed pause.
   - **Foreperiod (random wait).** The crosses keep showing for a
     *randomly chosen* short delay (different every trial, within a
     range set by the researcher). This randomness stops participants from
     predicting exactly when the stimulus will appear.
   - **Stimulus appears.** A box appears at one of the 2/3/4 positions. The
     participant presses the key that corresponds to that position as fast
     as they can.
   - **Feedback (practice only, optional).** If the study has "show practice
     feedback" turned on, an incorrect or missed (timed-out) response shows a
     brief "✗" before moving on. Correct responses never show feedback, and
     the test block **never** shows feedback regardless of this setting.
   - If the participant presses a response key **too early** — before the
     box appears — the wait is restarted with a new random delay, and (in
     practice only) the participant briefly sees a "Too soon!" message.

6. **Short break (interstitial screen).** After practice, there's a brief
   pause/transition screen before the real (test) trials begin.

7. **Test block.** The same trial structure repeats for the full number of
   test trials. This is the data used for the study's results. No feedback
   and no "Too soon!" messages are shown here — the participant just keeps
   responding trial after trial.

8. **Session complete.** Once all test trials are done, the participant sees
   a "Session complete" screen. **Participants never see their own results**
   — only researchers/admins can see scores and statistics.

### What if something goes wrong mid-session?

- **The participant accidentally exits full-screen, or switches to another
  tab/app** while waiting for or reacting to a stimulus: that one trial is
  thrown out and marked **invalid** (see Part 4). The participant sees a
  "click to continue" message, and an extra trial is added to the end of the
  block to make up for the lost one (up to 5 extra trials per block — a 6th
  problem in the same block is simply not made up).
- **The participant closes the tab, loses their connection, or refreshes the
  page:** when they come back and resume, the app picks up exactly where it
  left off — trials already recorded are not repeated.
- **A session sits "in progress" for over 30 minutes with no activity:** it's
  automatically marked **abandoned**. A researcher can **reset** it from the
  Sessions tab so the participant can try again. Resetting keeps the old data
  (tagged as a separate "attempt") and starts a fresh attempt.

---

## Part 2 — How reaction time is calculated

**Reaction time (RT) is the time between the stimulus box appearing on
screen and the participant pressing the correct/matching key**, measured in
milliseconds (ms), rounded to one decimal place (e.g. `318.4`).

A few important rules:

- **The clock starts the instant the box is actually drawn on screen** (the
  app uses the browser's most precise available timing for this, tied to the
  screen's own refresh — not just "when the computer decided to show it").
- **The clock stops the instant a *mapped* response key is pressed** (i.e.
  one of the keys assigned to the 2/3/4 response positions for this task).
  Pressing any other key does **not** stop the clock — see
  `extraneous_keys` below.
- **RT is recorded for both correct and incorrect responses** — i.e. if the
  participant presses *a* response key but the *wrong one*, you still get an
  RT for that trial, just with `outcome = incorrect`.
- **No RT is recorded for trials where the participant didn't respond in
  time** (`outcome = timeout`) or where the trial was thrown out
  (`outcome = invalid`) — the `rt_ms` cell is blank for these rows.

### Can reaction time ever be negative or measured from "before" the stimulus?

**No.** It is not possible for a recorded RT to be negative, or for a key
press made *before* the box appears to be counted as that trial's RT.

Here's why: if the participant presses a response key **before** the box
appears (during the resting/waiting period), that key press is **not timed
at all**. Instead:

- it's counted in the `premature_count` column (see Part 5), and
- the random waiting period is **restarted from scratch** with a brand-new
  random delay.

Only once the box actually appears does the RT clock start. So every
recorded RT is always a positive number of milliseconds *after* the box
appeared — there is no scenario in the data where RT is zero, negative, or
measured against an earlier point in time.

---

## Part 3 — Reading the `trials.csv` file

When you click **Export study data (ZIP)** on a study's page, you get a ZIP
file with four files. The most important one for analysis is **`trials.csv`
— one row per trial** (practice and test, every participant, every session,
every attempt).

Each row has these columns, in this order:

| # | Column | What it means |
|---|---|---|
| 1 | `study_name` | The study's name (for your reference — every row in the file is the same study). |
| 2 | `study_id` | The study's internal ID (a long code). Useful if you're combining files from multiple studies and want a guaranteed-unique key. |
| 3 | `task_type` | `CRT2`, `CRT3`, or `CRT4` — how many response positions/keys this session used. |
| 4 | `participant_code` | The participant's code (e.g. `PILOT-A7F3`). This is how you identify "who". |
| 5 | `session_code` | A code identifying this particular session (the participant may have several sessions, done on different days/visits). |
| 6 | `session_order` | Which session number this was for the participant (1st, 2nd, 3rd visit, etc.). Sessions are always completed in this order. |
| 7 | `attempt` | Which "try" at this session this row belongs to. Normally `1`. If a researcher **reset** the session and the participant redid it, you'll see rows with `attempt = 1` (the old, incomplete try) and `attempt = 2` (the redo). **For analysis, use only the highest `attempt` number for each `session_code`** — see Part 4. |
| 8 | `block` | `practice` or `test`. **Only `test` rows should be used for results** — practice trials are for the participant to warm up and are never analyzed. |
| 9 | `trial_index` | The trial's position within its block (1, 2, 3, …). |
| 10 | `stimulus_position` | Which of the 2/3/4 positions the box appeared at (0 = first position, 1 = second, etc.). |
| 11 | `foreperiod_ms` | How long (in ms) the random waiting period was *for this trial* before the box appeared. |
| 12 | `key_pressed` | The actual key the participant pressed to respond (blank if they didn't respond in time, or if the trial was thrown out). |
| 13 | `response_position` | Which position that key corresponds to (blank if no valid response). |
| 14 | `outcome` | One of: `correct`, `incorrect`, `timeout`, `invalid` — see Part 4. |
| 15 | `rt_ms` | The reaction time in milliseconds (blank for `timeout`/`invalid` rows). This is the main number you'll analyze. |
| 16 | `premature_count` | How many times the participant pressed a response key *too early* (before the box appeared) on this trial. See Part 5. |
| 17 | `extraneous_keys` | How many times the participant pressed a key that *isn't* one of the response keys, while waiting for or reacting to the stimulus. See Part 5. |
| 18 | `invalid_reason` | Why a trial was thrown out (blank unless `outcome = invalid`). See Part 5. |
| 19 | `outlier_flag` | `True`/`False` — whether this trial's RT is unusually fast or slow compared to the study's outlier thresholds. See Part 5. |
| 20 | `stimulus_onset_client_ms` | A technical timestamp marking exactly when the box appeared on the participant's screen, used internally to compute RT. See Part 5. |
| 21 | `session_started_at_iso` | When the participant started this session (date/time, UTC). |
| 22 | `session_completed_at_iso` | When the participant finished this session (date/time, UTC). Blank if not yet completed. |

> **Note on columns 21–22 after a reset:** these two timestamps always
> reflect the participant's **current/latest attempt** at the session — they
> are *not* per-row. If you're looking at old rows from `attempt = 1` of a
> session that was later reset and redone, the start/finish times shown will
> be from the redo (`attempt = 2`), not the original try. Use the `attempt`
> column to keep attempts straight; don't read these timestamps as "when this
> specific row happened."

---

## Part 4 — Which rows should be excluded from analysis?

The exported `trials.csv` is a **complete, unfiltered record** — it
deliberately includes everything, including practice trials, mistakes, and
throwaway data, so nothing is silently lost. **You need to filter it before
analyzing it.** The app's own built-in Dashboard/statistics already do this
filtering for you automatically — the rules below are exactly what the app
applies.

For a standard "what was this participant's reaction time" analysis, keep
**only** rows where **all** of the following are true:

1. **`block = test`** — discard all `practice` rows. Practice trials are
   warm-up only.
2. **`attempt` = the highest attempt number for that `session_code`** —
   discard rows from earlier, reset/abandoned attempts. (If a session was
   never reset, every row is `attempt = 1` and this doesn't matter.)
3. **`outcome = correct`** — discard:
   - `incorrect` rows (wrong key pressed — these have an RT, but it's not a
     "correct response time"),
   - `timeout` rows (no response at all — `rt_ms` is blank anyway),
   - `invalid` rows (the trial was interrupted/thrown out — `rt_ms` is blank
     anyway).

After applying rules 1–3, you have what the app calls the **"raw" RT
distribution** for that session — every correct, completed test-block
response.

4. **(Optional, for the "trimmed" analysis) `outlier_flag = False`** —
   additionally discard rows flagged as outliers (RTs that are unusually
   fast or unusually slow, per the study's configured thresholds). The app's
   summary statistics report both a **raw** mean (rules 1–3 only) and a
   **trimmed** mean (rules 1–4) side by side, so you can see the effect of
   removing outliers.

### Quick reference: what each `outcome` value means and whether to keep it

| `outcome` | What happened | `rt_ms` present? | Keep for RT analysis? |
|---|---|---|---|
| `correct` | Participant pressed the key matching the box's position | Yes | **Yes** — this is your primary data |
| `incorrect` | Participant pressed a *different* response key than the box's position | Yes | No (for RT). You may still want it for **accuracy** calculations — the app's accuracy % is `correct ÷ (correct + incorrect + timeout)` |
| `timeout` | Participant didn't press any response key before the response window closed | No (blank) | No for RT; counts as an error for accuracy |
| `invalid` | The trial was interrupted (e.g. participant left full-screen or switched tabs mid-trial) and was thrown out | No (blank) | No — exclude from everything; this trial's "slot" was redone as a later trial in the same block |

---

## Part 5 — The five "extra" columns explained

These five columns are the ones that often confuse people at first. Here's
what each one really means.

### `premature_count`

**How many times the participant pressed a response key *before* the box
appeared on this trial.**

- This counts presses during the resting/waiting period *before* the
  stimulus shows up.
- It only counts presses of the actual **response keys** (the ones used for
  the 2/3/4 positions) — pressing some unrelated key during the wait does
  *not* increase this; that goes into `extraneous_keys` instead.
- Each early press **restarts the random wait with a new random delay** —
  so a participant who jumps the gun repeatedly will see the wait reset
  again and again, and `premature_count` will go up by 1 each time.
- It resets to 0 for every new trial.
- **Normal value: 0.** A non-zero value means the participant responded
  before the stimulus appeared at least once on that trial — this doesn't
  invalidate the trial (the eventual RT is still timed correctly from the
  *new* stimulus onset), but a participant with consistently high
  `premature_count` values may be guessing/anticipating rather than
  reacting, which is worth noting.
- The Dashboard's session summary also reports a **total premature count**
  for the whole test block — that's just the sum of this column across all
  `test` rows for that attempt.

### `extraneous_keys`

**How many times the participant pressed a key that is *not* one of the
task's response keys, at any point during this trial (before or after the
stimulus appears).**

- Examples: accidentally pressing Tab, Caps Lock, a number key, etc., when
  the task only uses, say, the F and J keys.
- These presses are simply **ignored** by the task — they don't end the
  trial, don't affect timing, and don't change `outcome`. They're only
  *counted* here so you can see if a participant was fumbling around on the
  keyboard.
- **Normal value: 0.** Occasional 1s are harmless. A participant with high
  values across many trials may have been confused about which keys to use,
  or resting their hands on extra keys.

### `invalid_reason`

**Why a trial was thrown out (only filled in when `outcome = invalid`;
blank otherwise).**

Two possible values:

- **`fullscreen_exit`** — the participant exited full-screen mode (e.g.
  pressed Esc, or used a keyboard shortcut to switch apps/windows) while a
  trial was in progress (waiting for, or reacting to, the stimulus).
- **`focus_loss`** — the browser tab/window lost focus (e.g. the
  participant clicked on another application, or the operating system
  showed a notification) during the waiting/reacting period of a trial.

In both cases:
- That trial's data is discarded (no `rt_ms`, `outcome = invalid`).
- The participant sees a message asking them to return to full-screen before
  continuing.
- The app automatically adds one extra trial at the end of the block so the
  block still ends up with the intended number of *usable* trials (up to 5
  extra per block; a 6th interruption in the same block is not made up for).

**A study with many `invalid` rows** for one participant may indicate they
were repeatedly distracted, switching tabs, or having trouble keeping the
browser in full-screen — worth a note if it's frequent.

### `outlier_flag`

**`True` if this trial's reaction time is unusually fast or unusually slow
compared to the study's configured "normal" range; `False` otherwise.**

- This is only ever `True` for `outcome = correct` rows — incorrect,
  timeout, and invalid rows are never flagged (they don't have an RT to
  judge).
- The "normal range" (an upper and lower RT bound, in ms) is set per study by
  the researcher when the study is configured. Any correct-trial RT outside
  that range gets `outlier_flag = True`.
- These rows are **not deleted** — they remain in the data with their real
  `rt_ms` value. They're just flagged so that the "trimmed" statistics (which
  exclude them) can be compared against the "raw" statistics (which include
  them). Use this column if you want to reproduce the app's trimmed
  calculations yourself, or to apply your own outlier criteria instead.

### `stimulus_onset_client_ms`

**A precise timestamp (in milliseconds) marking the exact moment the
stimulus box appeared on the participant's screen, on the participant's own
computer clock.**

- This is the "starting gun" for the RT measurement — `rt_ms` is essentially
  "how much later did the key press happen, compared to this number".
- **You generally don't need to use this column directly** — it's recorded
  mainly for technical auditing/troubleshooting (e.g. if a researcher ever
  needs to double-check the raw timing data behind an `rt_ms` value).
- It's blank only for `timeout`/`invalid` rows where, in rare edge cases, the
  stimulus never finished being drawn before the trial ended.
- The numbers themselves aren't meaningful "wall clock" times (they're not
  the same as `session_started_at_iso`) — they're just a running clock on
  the participant's machine, useful only for *comparing two timestamps within
  the same session*.

---

## Summary cheat-sheet

- **Use `trials.csv`, filter to `block = test`, latest `attempt`,
  `outcome = correct`** for your main RT analysis.
- **`rt_ms`** = time from stimulus appearing to the correct key being
  pressed. Always positive, never measured from before the stimulus.
- **`premature_count`** = early presses *before* the stimulus, on this
  trial — each one redraws the random wait. 0 is normal.
- **`extraneous_keys`** = wrong/irrelevant key presses during the trial —
  ignored by the task, just a tally. 0 is normal.
- **`invalid_reason`** = why a trial was thrown out
  (`fullscreen_exit`/`focus_loss`); only present when `outcome = invalid`.
- **`outlier_flag`** = `True` if a *correct* trial's RT is outside the
  study's configured normal range; used to compute "trimmed" stats.
- **`stimulus_onset_client_ms`** = technical timestamp, safe to ignore unless
  auditing raw timing.
