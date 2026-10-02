---
name: quiz
description: Run a practice quiz on a course or exam from the files in materials/. Use when the user asks to be quizzed, wants practice questions, or says "/quiz ACCY 301" or "/quiz PSYC 475 exam 2".
---

# Practice quiz

Arguments: a course, optionally an exam or topic, optionally a number of questions (default 10).

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

## Scope
1. Read `materials/COURSE_GUIDE.md` and `study.toml`.
2. If an exam is named, limit the scope to that exam's `covers` patterns (the same files
   `uv run canvas-sync pack "<exam>"` would collect). If a topic is named, find the files on that topic.
   With neither, use the next upcoming exam for the course.
3. Read the actual files in scope before writing anything. Do not write questions from memory or from
   general knowledge of the subject; every question must be answerable from these materials.

## Format
Match how the course tests. Look at its practice exam, study guide or exam review first.
- PSYC 475: multiple choice, four options, concept and application.
- BADM 210: multiple choice, true/false and calculated numeric answers.
- ACCY 301 / ACCY 302: short computational problems and short concept questions. For long multi-part
  problems use the `big-question` skill instead.
Weight topics the way the study guide or review session does. Use new numbers and new scenarios; never
copy a question from the practice materials.

## Running it
- Ask one question at a time and wait for the answer.
- After each answer: say right or wrong, give the correct answer with the reasoning, and cite the source
  as course, file and slide or page.
- Check every numeric answer by computing it with a short script before stating it.
- At the end: score, the topics missed, and which files to reread for each.
- If the user asks for a quiz "to save" or "to print", write the questions to
  `study/generated/<course> quiz <date>.md` and the answer key to a separate `... answers.md` instead.

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
