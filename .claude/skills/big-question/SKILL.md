---
name: big-question
description: Write a new long, multi-part exam-style problem (the kind on accounting practice exams) with a verified worked solution. Use when the user asks for a big question, a long problem, a practice-exam-style problem, or says "/big-question ACCY 302 activity-based costing".
---

# Big exam-style question

Arguments: a course, optionally a topic, optionally how many problems (default 1).

## Learn the format from the course's own problems
Before writing, read the course's practice exam and in-class practice problems in `materials/<course>/`
(for ACCY 302: the Midterm practice problems and "In Class Practice" files; for ACCY 301: the practice
exam, chapter exercises and their solutions). Problems in these courses look like this:
- A short topic title (for example "Activity-Based Costing").
- A named fictional company and a paragraph of business context.
- One to three data tables (cost pools and drivers, inventories, department hours, per-unit costs).
- "Required:" followed by three to five numbered parts. Later parts build on earlier ones, and the last
  part usually asks for an explanation or a recommendation rather than a number.
- Some problems hide a figure that must be worked backward from the others.

## Write a new one
- Topic: the one requested, otherwise one covered by the next exam in `study.toml`. Only use methods
  that appear in the course's slides or practice files; cite the file the method comes from.
- New company, new industry and new numbers every time. Never reuse a scenario or a data table from the
  course materials or from an earlier generated problem in `study/generated/`.
- Pick numbers that work out cleanly (whole-dollar rates, sensible totals), at the same difficulty and
  length as the course's own problems.
- Lay out the data in Markdown tables.

## Verify before showing anything
Solve the problem with a short Python script and confirm every figure in the solution matches the
script's output. If a number comes out messy or a part turns out ambiguous, change the problem and
solve it again. Do not present a problem whose solution has not been checked this way.

## Deliver
- Save the problem to `study/generated/<course> <topic> <date>.md` and the worked solution to a separate
  `... solution.md`, so the user can attempt it without seeing the answer.
- Show only the problem in chat. Do not reveal the solution until the user answers or asks for it.
- The solution has: each part worked step by step with the formula used, the final answers, the source
  file for the method, and the mistakes students most often make on this type of problem.
- When the user submits an attempt, grade it part by part, show where the first error occurred, and
  carry their error forward to see whether later parts were otherwise right.
