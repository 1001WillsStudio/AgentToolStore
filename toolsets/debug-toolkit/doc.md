# debug

---
name: debug
description: Systematic debugging and troubleshooting for code issues, test failures, build errors, runtime exceptions, and unexpected behavior. Use when diagnosing bugs, investigating test failures, analyzing error logs, fixing build breaks, or troubleshooting any malfunction.
---

# Debug

A systematic approach to debugging and troubleshooting.

## The Debug Process

### 1. Gather Information

Before attempting a fix, understand the problem:
- **What is the symptom?** Error message, unexpected output, crash, hang?
- **When did it start?** After a specific change? Intermittent or consistent?
- **What is the scope?** One file, one function, system-wide?
- **What are the relevant artifacts?** Stack traces, logs, test output, screenshots?

Collect ALL available information before hypothesizing.

### 2. Reproduce

- Can you reproduce the issue reliably?
- What are the minimal reproduction steps?
- Does it happen in all environments or only specific ones?

### 3. Isolate

Narrow the problem space:
- Binary search: comment out half the code, test, repeat
- Simplify: reduce to minimal test case
- Diff: compare working vs. non-working versions
- Trace: follow the execution path with logging/prints

### 4. Hypothesize

Form a specific, falsifiable hypothesis:
- "The bug is in function X because..."
- "The test fails because Y is null when..."

Test your hypothesis before acting on it.

### 5. Fix

- Make the minimal change that addresses the root cause
- Verify the fix resolves the original issue
- Check that nothing else broke (run related tests)
- Consider: does this fix reveal a broader pattern that needs addressing?

### 6. Prevent

- Add a test that would have caught this bug
- Document any non-obvious behavior
- Consider: could similar bugs exist elsewhere?

## Common Debug Patterns

### Build/Compilation Errors
1. Read the FIRST error (subsequent errors are often cascading)
2. Check imports, types, syntax before logic
3. Verify dependency versions

### Runtime Errors
1. Identify the exact line from the stack trace
2. Check null/undefined values
3. Verify assumptions about input data
4. Add logging to trace the flow

### Test Failures
1. Read the assertion error carefully — expected vs. actual
2. Check test setup and teardown
3. Is the test correct? Sometimes the test has the bug.

### Performance Issues
1. Measure before optimizing
2. Identify the bottleneck (profiling, timing)
3. Focus on the hottest path

## When Debugging Isn't Working

If you've been debugging for a while without progress:
- **Step back**: Are you debugging the right thing?
- **Explain it**: Articulate the problem out loud (rubber duck debugging)
- **Fresh eyes**: Look at it from a completely different angle
- **Ask for help**: Describe what you've tried and what you're stuck on
- **Take a break**: Sometimes the answer comes after stepping away

## Guidelines

- **Don't guess**: Form a hypothesis and test it before making changes
- **One change at a time**: If you change 5 things and it works, you don't know which fixed it
- **Keep notes**: Track what you've tried and what happened
- **Read error messages carefully**: They often tell you exactly what's wrong
- **The simplest explanation is usually correct**: Check the obvious things first
