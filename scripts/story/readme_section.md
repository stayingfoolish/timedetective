## One question, followed all the way

> **{{question}}**

A student asks this about the farm belt of north-west India: Punjab, Haryana, Delhi and northern Rajasthan.
TimeDetective answers from {{years_round}} years of NASA satellite data.

**The groundwater estimate is falling about {{slope}} cm of water a year (range {{slope_range}}), about {{total}} cm in
total, and the fields do not show it.** The label on that answer is **significant**.

What it cannot say is whether the water is running out. The satellites measure how much the stored water changes,
not how much is left.

<img src="docs/images/story/fields.png" alt="Two panels for north-west India, {{green_y0}} to {{green_y1}}. The groundwater estimate falls steadily while the greenness of the land rises.">

Here is how it got there, one question at a time. Questions 1 to 6 are the six steps of one playbook, and each
step is one procedure. Questions 7 and 8 are where the tool stops. Question 9 runs the same playbook somewhere else.

**[Open the interactive version]({{pages}})** to hover over any chart and see the numbers behind it, or run it
live with `make demo`, which opens on this walkthrough.

### 1. How can anyone know what is underground?

By weighing it from orbit. Two satellite missions, GRACE and then GRACE-FO, run by NASA with German partners,
measure tiny changes in Earth's gravity as water moves around. That gives the change in all the water stored in a
region. A NASA land model, GLDAS, estimates the soil moisture and snow. Subtract that, and what is left is an
estimate of groundwater, counted in centimetres of water: a layer that deep spread over the whole region.

<img src="docs/images/story/q1_subtract.png" alt="Monthly lines for north-west India, {{y0}} to {{y1}}: all stored water, modelled soil moisture and snow, and the difference, which is the groundwater estimate.">

<img src="docs/images/story/q1_region.png" alt="The region as {{cells}} measurement blocks, with what the first step found: {{years}} years of record, {{months}} of {{months_all}} months with data.">

{{step1}}

### 2. Is it actually falling?

Yes. With the yearly cycle of monsoon and dry season removed and each year averaged, the estimate goes from
{{v0}} cm in {{y0}} to {{v1}} cm in {{y1}}.

<img src="docs/images/story/q2_annual.png" alt="The groundwater estimate for north-west India, one value per year, falling from {{y0}} to {{y1}}.">

{{step2}}

### 3. Is that real, or could it be noise?

It is larger than chance would explain. A fitted line cannot answer this, because a line can be fitted to
anything, and records like this one wander: a wet year leaves the ground wetter the next year too, so a record with
no trend can drift one way for a decade. The test used here ignores the line. It takes the change from each year to
the next and asks whether those changes average out to zero.

They do not. The average is a fall of {{mean_change}} cm a year, nearly as large as the usual swing from one year to
the next ({{sd}} cm), and the test's p-value is {{p}}.

<img src="docs/images/story/q3_changes.png" alt="Bars showing the change in the groundwater estimate from each year to the next. Most point down, and the average is a fall of {{mean_change}} cm a year.">

{{step3}}

### 4. Could it be the satellites and not the water?

The check finds no clear sign of it, though this is the closest call here. The record comes from two missions with
{{gap_months}} months between them, and a small offset between them would look like a decline. Step 4 measures the
change across that gap, after taking out the overall slide, and compares it with every other stretch of the same
length. {{as_large}} of {{n_plac}} stretches ({{share}}%) moved as much. The bar for raising a caution is 1 in 20, and
this does not pass it.

<img src="docs/images/story/q4_gap.png" alt="Histogram of the change across {{n_plac}} stretches of the record, with the real mission gap marked in the lower tail.">

{{step4}}

### 5. Is it just a dry spell?

No. Rainfall rose over the period, and the water still fell. In a spell of exactly average rainfall, storage still
fell about {{at_avg}} cm a year (range {{at_avg_range}}).

<img src="docs/images/story/q5_rain.png" alt="Each year's change in storage against the rain of the same two years. The fitted line is still well below zero at average rainfall.">

{{step5}}

### 6. Would you see it from the fields?

No. This is the chart at the top: over {{green_y0}} to {{green_y1}} the land got greener, by about {{green}} NDVI a
decade, while the water under it fell. NDVI is a satellite measure of green plant cover, from NASA's MODIS
instrument.

{{step6}}

### 7. So why is it falling?

TimeDetective does not say. Asked why, it runs the same six steps and adds two sentences to the finding:

> {{cause1}}.
>
> {{cause2}}.

The 2009 study in Nature by Rodell, Velicogna and Famiglietti concluded that pumping for irrigation was the likely
cause. That is their conclusion. Testing it needs pumping records, and no step in this playbook has any. A tool
that printed "caused by irrigation" here would be repeating a paper, not checking one.

### 8. What about my district?

It refuses, at the first step, before any trend is computed. A district such as {{district}} is smaller than one
of the satellites' blocks, and even {{hot_n}} blocks cannot be separated from the land around them.

<img src="docs/images/story/q8_district.png" alt="The {{hot_n}} blocks nearest {{district}} highlighted on the map, beside the refusal: the region spans {{hot_n}} resolution cells and about {{cells_min}} are needed.">

### 9. Is it the same in Kansas?

Same six steps, different label. Over the US High Plains a straight line falls about {{hp_slope}} cm a year (range
{{hp_range}}), but the test does not fire (p = {{hp_p}}), so the tool reports the slope as a description and says a
record that simply wanders could look like this. There the average yearly fall ({{hp_mean}} cm) is about half the
usual swing ({{hp_sd}} cm).

<img src="docs/images/story/q9_compare.png" alt="North-west India and the US High Plains side by side on the same scale: yearly groundwater estimates above, year-to-year changes below.">

A widely used test, prewhitened Mann-Kendall, does fire here (p = {{hp_p2}}). It also fired on 21 to 26% of
wandering records with no trend when we measured it, so it does not get to decide. The strictness has a price: the
tool will sometimes hold back on a decline that is real.

### How the label was decided

Procedures never choose the label. They record evidence, and one module, the critic, applies a fixed rule to it.

{{checks_md}}

### The playbook and its procedures

The order of the six steps is a data file, [`{{playbook_path}}`]({{playbook_path}}). Every arrow in it names the
source of the rule that justifies it, and the engine rejects an arrow that has none.

<img src="docs/images/story/playbook.png" alt="Flow diagram of the playbook: audit, annual, trend, handover, rainfall, greenness, then the finding. The first four steps can each end in a refusal.">

{{procedures_md}}

Each procedure is a short definition file plus one function that does the arithmetic. No AI model runs inside any
of them.

<img src="docs/images/story/procedure.png" alt="The definition file for storage_rainfall beside what it returned for north-west India.">

Every figure in this walkthrough is written out by the code: `uv run python scripts/story/extract.py`, then
`uv run python scripts/story/build_page.py`.
