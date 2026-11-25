# Skill: Hard Coding (Smart & Free)

## When to use
Building apps, scripts, websites, tools, refactors, bug fixes, automation — anything that ends in code, in ANY programming language.

## Smart & free workflow
1. **Clarify the win condition**: what must exist and work when done. Write it as a short checklist.
2. **Architecture first (local brain)**: pick language, libraries (prefer stdlib + battle-tested free packages), file layout. Keep it SIMPLE: the smallest thing that fully works.
3. **Heavy lifting (free muscle)**: send precise, self-contained prompts to a gateway big model or web deck — full file contents in, full file out. Ask for complete, runnable code, no placeholders, no "TODO".
4. **Execute & test locally (the edge)**: write files with the file tools, run them with the shell tool, capture errors.
5. **Self-repair loop**: on failure, feed the exact error + failing code back to the model. Max 3 iterations per bug, then split the problem smaller.
6. **Verify the win condition**: run the checklist. Test edge cases (empty input, unicode, big files, no network).
7. **Package**: README with run steps, or a .bat/.sh launcher. Tell the user exactly how to run it.

## Prompting the muscle (how to get great code free)
- Include: goal, language+version, libraries, existing code, exact error messages, expected vs actual behavior, constraints.
- Demand: complete files (not snippets), error handling, and a one-line "how to run".
- For big apps: generate module by module, run each before moving on.

## Quality bar
- Code must RUN. Never deliver untested code when a shell is available.
- Prefer standard, maintained, permissively-licensed dependencies.
- Cross-platform where free (pure Python/Node/HTML beat exotic stacks).
- If a task needs a compiler/toolchain, check availability first with the shell tool; report what's missing instead of failing silently.
