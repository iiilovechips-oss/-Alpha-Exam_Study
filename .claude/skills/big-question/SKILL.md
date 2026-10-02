---
name: big-question
description: Write a new long, multi-part exam-style problem (the kind on accounting practice exams) with a verified worked solution. Use when the user asks for a big question, a long problem, a practice-exam-style problem, or says "/big-question ACCY 302 activity-based costing".
---

# Big exam-style question

Arguments: a course, optionally a topic, optionally how many problems (default 1).

## Ask where the user is first
Before explaining, quizzing or writing a problem, find out how well the user already knows the topic.
1. Read `study/LEVELS.md`. If the topic has a rating there, use it and do not ask again.
2. If it is missing, ask one short question: roughly what percent of this topic do they feel they
   understand (0% = never seen it, 100% = could teach it)? Offer, as an option, a 5-question check on the
   core ideas if they are not sure. Do not force the check; a self-rating is enough to start.
3. Save the answer as a new row in `study/LEVELS.md` with today's date. Update the row when the user gives
   a new rating or when quiz results clearly show a different level.

Then match the depth to the level:
- **Under 30% (new to it):** assume nothing. Start from what the topic is for, build each idea on the one
  before, define every term, show a tiny example before the real one, and go slowly through every step of
  a calculation or journal entry. Say what must be understood before moving on.
- **30% to 70% (partly there):** a quick reminder of the basics, then spend the time on the parts that
  usually cause mistakes.
- **Over 70% (mostly solid):** keep it brief. Focus on traps, exceptions and exam-style practice.

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
- Keep it as direct as a real exam problem. Default shape: a short setup, one block of data, and two
  to four required items that each ask for one number or one journal entry (for example "What is the
  balance of gross accounts receivable?"). No "ignore part 2" branches, what-if variations, embedded
  side transactions or essay parts unless the user asks for a harder or longer problem. Do not make it
  longer or more layered than the problems on the course's own practice exam.
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

## Use homework, quizzes and projects as evidence of what gets tested
The study packs leave out graded work, but it is still in `materials/<course>/`. Before choosing topics,
also read the homework, quiz, case and mini-project pages and files for the chapters or weeks in scope
(including the saved Canvas pages, the `.md` files). Topics and problem types that show up there are
likely exam material, so weight them more heavily. In BADM 210 the mini-projects are tested on exams.
Use them only to decide what to ask and at what difficulty: write new questions, never hand back a
graded assignment's own questions or answers.

## Material that lives outside Canvas
Some homework is on sites this tool cannot reach, so it is missing from `materials/` unless the user
adds it:
- ACCY 301: McGraw-Hill Connect (homework, quizzes, SmartBook)
- BADM 210: PrairieLearn (homework)
- ACCY 302: the online homework quizzes inside Canvas (quiz questions are not collected)

When the user asks for a study guide, quiz, big question or exam prep for one of these courses, say once,
briefly, that those homework questions are not included and that adding them would make the result
closer to the real exam. Tell them how: save or print the homework pages (PDF or screenshots) into
`materials/<course>/Homework/`, or paste the questions into the chat. Files in that folder are picked up
by the export, the study packs and these skills. Then carry on with what is available; do not block on it
and do not repeat the reminder later in the same conversation.
