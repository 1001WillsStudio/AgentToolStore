# skill-creator

---
name: skill-creator
description: Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a skill from scratch, edit or optimize an existing skill, run evals to test a skill, benchmark skill performance, or optimize a skill's description for better triggering accuracy.
---

# Skill Creator

A skill for creating new skills and iteratively improving them.

## Overview

The skill creation process follows a cycle:

1. Decide what the skill should do and roughly how
2. Write a draft
3. Create test prompts and run the agent with the skill on them
4. Evaluate results qualitatively and quantitatively
5. Rewrite based on feedback
6. Repeat until satisfied
7. Expand the test set and try at larger scale

Your job: figure out where the user is in this process and help them progress.

---

## Creating a Skill

### 1. Capture Intent

Start by understanding the user's intent. If the current conversation already contains a workflow to capture, extract from the history — tools used, sequence of steps, corrections made, input/output formats observed.

Answer these questions:
- What should this skill enable the agent to do?
- When should this skill trigger? What user phrases/contexts?
- What's the expected output format?
- Should we set up test cases? (Objectively verifiable outputs benefit from tests; subjective outputs like writing style often don't.)

### 2. Interview and Research

Proactively ask about edge cases, input/output formats, example files, success criteria, and dependencies. Research in parallel if tools are available.

### 3. Write the SKILL.md

Fill in these components:

- **name**: Skill identifier (lowercase, hyphens, max 64 chars)
- **description**: When to trigger + what it does. This is the PRIMARY triggering mechanism. Include both what the skill does AND specific contexts for when to use it. Make descriptions slightly "pushy" — agents tend to under-trigger skills.
- **compatibility**: Required tools/dependencies (optional, rarely needed)
- **Body**: Instructions, examples, guidelines

#### Anatomy of a Skill

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description required)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/    - Executable code for deterministic/repetitive tasks
    ├── references/ - Docs loaded into context as needed
    └── assets/     - Files used in output (templates, icons, fonts)
```

#### Progressive Disclosure

Skills use three-level loading:
1. **Metadata** (name + description) — Always in context (~100 chars)
2. **SKILL.md body** — In context when skill triggers (<500 lines ideal)
3. **Bundled resources** — As needed (unlimited)

#### Writing Patterns

- Prefer imperative form ("Do X") for instructions
- Explain WHY things matter rather than heavy-handed MUSTs
- Include concrete Input/Output examples
- For >500 lines, add hierarchy with clear pointers to next steps

#### Domain Organization

When a skill supports multiple domains:
```
cloud-deploy/
├── SKILL.md (workflow + selection)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```
The agent reads only the relevant reference file.

---

## Testing and Evaluation

### Test Cases

After writing the skill draft, create 2-3 realistic test prompts. Save to `evals/evals.json`:

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt",
      "expected_output": "Description of expected result",
      "files": []
    }
  ]
}
```

### Running Tests

For each test case, run the agent with the skill on the prompt. Collect:
- Output files
- Token usage
- Duration

### Grading

Define quantitative assertions for objectively verifiable outputs:

- Assertions should have descriptive names
- Each assertion checks one specific thing
- Use programmatic verification where possible (scripts > eyeballing)

### The Iteration Loop

1. Apply improvements to the skill
2. Rerun all test cases
3. Review results with the user
4. Read feedback
5. Improve again

Stop when:
- The user says they're happy
- All feedback is empty (everything looks good)
- You're not making meaningful progress

---

## Improving Skills

### How to Think About Improvements

1. **Generalize from feedback**: Create skills that work across many prompts, not just test examples. Avoid fiddly, overfit changes.
2. **Keep it lean**: Remove things that don't pull their weight. Read transcripts, not just final outputs.
3. **Explain the why**: Today's agents are smart — they benefit from understanding reasoning, not just rigid rules. If you find yourself writing ALWAYS or NEVER in all caps, that's a yellow flag.
4. **Look for repeated work**: If all test cases result in the same helper script being written, bundle that script in `scripts/`.

---

## Description Optimization

The `description` field is the primary mechanism for skill triggering. After creating a skill, optimize it.

### Process

1. **Generate trigger eval queries** (~20 total):
   - 8-10 should-trigger queries (various phrasings, formal + casual)
   - 8-10 should-not-trigger queries (near-misses, adjacent domains)
   - Queries should be realistic, concrete, with specific details

2. **Review with user**: Get sign-off on eval queries

3. **Run optimization**: Test the description against queries, iterate to improve triggering accuracy

### How Triggering Works

Agents see skill names + descriptions and decide whether to consult a skill. They tend to:
- **Trigger on**: Complex, multi-step, specialized tasks
- **NOT trigger on**: Simple one-step tasks they can handle with basic tools

Design eval queries that are substantive enough to actually benefit from a skill.

---

## Skill Writing Guide

### Principle of Lack of Surprise

Skills must not contain malware, exploit code, or content that could compromise security. A skill's contents should not surprise the user in their intent.

### Writing Style

- Explain WHY things are important
- Use theory of mind — help the agent understand the user's actual goals
- Make skills general, not super-narrow to specific examples
- Write a draft, then look at it with fresh eyes and improve it

### Communication

Pay attention to context cues about the user's technical level. Default to:
- "evaluation" and "benchmark" are borderline OK
- "JSON" and "assertion" need serious cues before using without explanation
- Briefly explain terms if in doubt
