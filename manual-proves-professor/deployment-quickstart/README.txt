JUTGE DEPLOYMENT QUICK START
============================

CONTENTS
- quickstart.json: importable bundle with five topics and five exercises.
- solutions/: reference C solutions for all exercises.
- solutions/t4_pipes_solution.zip: ZIP submission for the Makefile exercise.

LOAD THE EXERCISES
1. Open the teacher admin panel and select the subject where you want the examples.
2. Open "Importacio completa".
3. Import quickstart.json. The importer creates the topics/exercises/tests under the selected subject.
4. Open each exercise as a student and submit its matching solution from solutions/.
   For "Quatre fills escriuen per pipe", submit t4_pipes_solution.zip.

COVERAGE
- C basics: exercise arguments + per-test arguments + stdin; exact and lines comparison.
- Processes: fork/wait and ordered line comparison.
- File I/O: teacher-provided text and binary fixtures, arguments for filenames,
  expected generated files, regex stdout comparison, and downloadable artifacts.
- Pipes: ZIP/Makefile submission, project resource plus teacher fixture override,
  fork/pipe/read/write/close/wait, unordered token comparison.
- Signals: children raise SIGUSR1; unordered line comparison.
- Static analysis: required/forbidden calls, minimum counts, required pairs and
  teacher-only advisory reports. Findings never change AC/WA.

LIMITS / NOTES
- The signal example raises SIGUSR1 within its own child processes. Jutge does not
  yet inject external signals into a running submission.
- Static checks are heuristic text-pattern checks, not an AST or semantic proof.
- Fixture paths are relative to the test working directory. Teacher fixtures
  replace ZIP resources with the same path for that test only.
- The Makefile ZIP must contain Makefile, main.c and count.txt at its root.
