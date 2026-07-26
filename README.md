# QueueCTL

A production-inspired CLI-based background job queue built with **Python**, **SQLite**, and **Typer**.

QueueCTL allows users to enqueue shell commands, process them concurrently using multiple workers, automatically retry failed jobs using configurable exponential backoff, and manage permanently failed jobs through a Dead Letter Queue (DLQ).

---

## Features

- Persistent SQLite-backed job queue
- Concurrent worker processing (`--count N`)
- Atomic job claiming (prevents duplicate execution)
- Automatic retries with configurable exponential backoff
- Runtime configurable retry count and backoff base
- Dead Letter Queue (DLQ)
- Queue status reporting
- Job listing with state filtering
- Comprehensive automated test suite (37 tests)

---

## Tech Stack

- Python 3
- SQLite
- Typer
- Pytest

---

# Architecture

```
                    +----------------------+
                    |      CLI (Typer)     |
                    +----------+-----------+
                               |
               +---------------+---------------+
               |                               |
               v                               v
     +-------------------+           +-------------------+
     | Runtime Config    |           | SQLite Database   |
     | config.py         |           | db.py             |
     +-------------------+           +---------+---------+
                                               |
                                               |
                                     +---------v---------+
                                     |     Job Queue     |
                                     +---------+---------+
                                               |
                       +-----------------------+-----------------------+
                       |                                               |
                       v                                               v
                Worker Process 1                               Worker Process N
                       |                                               |
                       +-----------------------+-----------------------+
                                               |
                                               v
                                       Job State Machine
```

---

# Job Lifecycle

```
Pending
   |
   v
Processing
   |
   +-------------------------+
   |                         |
Success                   Failure
   |                         |
   v                         v
Completed              Retry Scheduled
                             |
                     Exponential Backoff
                             |
                    Retries Remaining?
                       |             |
                      Yes           No
                       |             |
                       v             v
                    Pending       DEAD (DLQ)
```

---

# Setup Instructions

Clone the repository:

```bash
git clone https://github.com/Prashant-00000/queuectl.git
cd queuectl
```

Create a virtual environment:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Usage Examples

> **Note for Windows PowerShell users:** PowerShell mangles embedded double
> quotes when passing arguments directly to `python.exe`. If a command
> below fails with a JSON parsing error, use the stop-parsing operator
> instead:
> ```powershell
> python -m queuectl.cli enqueue --% "{\"id\":\"job1\",\"command\":\"echo hi\"}"
> ```
> On Linux/macOS bash, the single-quoted form shown below works as-is.

## Start workers

```bash
queuectl worker start --count 3
```

Spawns the requested number of worker processes, each polling SQLite independently. Jobs are claimed atomically, so no job is ever processed by more than one worker.

## Stop workers

Press `Ctrl+C` in the terminal running the worker(s). Each worker is given up to 5 seconds to finish its current job before being terminated, satisfying graceful shutdown.

---

## Enqueue a job

```bash
queuectl enqueue '{"id":"job1","command":"echo Hello QueueCTL"}'
```

The `id` field is optional — if omitted, a UUID is generated automatically.

---

## Queue status

```bash
queuectl status
```

Example:

```
Queue Status
------------

Pending:      2
Processing:   1
Completed:    9
Dead:         1

Total Jobs: 13
```

---

## List jobs

```bash
queuectl list
queuectl list --state pending
```

---

## Dead Letter Queue

List dead jobs:

```bash
queuectl dlq list
```

Retry a dead job:

```bash
queuectl dlq retry job1
```

Retrying a job that isn't in the `dead` state fails with a clear error rather than a traceback.

---

## Runtime Configuration

View configuration:

```bash
queuectl config get max_retries
queuectl config get backoff_base
```

Update configuration:

```bash
queuectl config set max_retries 5
queuectl config set backoff_base 3
```

Configuration is stored in the same SQLite database as job data, so changes are persisted and immediately affect newly created jobs and future retry scheduling.

---

# Retry Strategy

Failed jobs are retried automatically using exponential backoff.

```
delay = backoff_base ^ attempts
```

Example (`backoff_base = 2`):

| Attempt | Delay |
|---------|------:|
| 1 | 2 s |
| 2 | 4 s |
| 3 | 8 s |

After the configured `max_retries` is reached, the job transitions to `dead` and moves into the Dead Letter Queue. Retry delays are capped at **60 seconds** to prevent unbounded wait times — a standard production pattern beyond the literal formula.

---

# Dead Letter Queue

Jobs that permanently fail after exhausting all retries transition to the `dead` state and are managed through the DLQ.

Available commands:

```bash
queuectl dlq list
queuectl dlq retry <job_id>
```

Retrying a DLQ job resets its attempt count and `next_run_at`, then moves it back to `pending`. If the underlying command is still invalid, the job will simply fail and return to the DLQ again — retrying does not fix a bad command, it re-attempts it.

---

# Assumptions & Trade-offs

- **SQLite over a dedicated message broker** — chosen to keep the project self-contained and dependency-free while still providing durable persistence and transactional guarantees. WAL mode plus a `busy_timeout` pragma handle concurrent access from multiple worker processes.
- **Atomic job claiming** — a job is claimed via a single `UPDATE ... WHERE state = 'pending' ... RETURNING *` statement rather than a separate read-then-write, so two workers can never claim the same job. This relies on SQLite's writer serialization, backed by the busy-timeout pragma so concurrent claims wait instead of erroring.
- **Command execution via `shell=True`** — job commands are run with `subprocess.run(job.command, shell=True, capture_output=True, text=True)`, which allows shell features (pipes, `&&`, redirection) in a job's command string. The trade-off is that this trusts the command string; it's an acceptable choice for a queue whose jobs are enqueued by a trusted operator, but would need hardening (e.g. `shlex.split()` with an explicit argv list, or a sandboxed executor) before accepting job commands from untrusted external input.
- **Runtime configuration in SQLite, not a config file** — `max_retries` and `backoff_base` live in the same database as job data, so `queuectl config set` takes effect immediately, requires no restart, and stays correctly scoped to whichever database a given worker or CLI invocation is actually operating on.
- **Retry delays capped at 60 seconds** — prevents unbounded exponential growth for jobs with a high `max_retries`.
- **The `failed` state is reserved but not currently used as a terminal state** — the job lifecycle transitions directly from a failed execution to either `pending` (retry) or `dead` (exhausted), matching the assignment's state table. `failed` remains in the `JobState` enum for potential future use.
- **Multiple workers run as separate OS processes** (via `multiprocessing`), each independently polling and atomically claiming jobs — this is what guarantees no job is ever processed twice even under concurrent load.

---

# Testing Instructions

Run the automated test suite:

```bash
pytest -v
```

Current status:

```
37 passed
```

The tests cover:

- CLI commands (enqueue, worker, status, list, dlq, config)
- Database operations (add, claim, update, list)
- Atomic job claiming under concurrent access
- Worker execution (success and failure paths)
- Retry logic and attempt counting
- Exponential backoff scheduling (including config-driven values)
- Runtime configuration (`get`/`set`), correctly isolated per database path
- Dead Letter Queue operations (list, retry, invalid-state retry)
- Queue status reporting
- Multi-worker process spawning (`--count`)
- Job persistence across restarts

### Manual Verification

1. Start workers: `queuectl worker start --count 3`.
2. In another terminal, enqueue a successful command and verify it completes:
   `queuectl enqueue '{"command":"echo hello"}'`
3. Enqueue a job with an invalid command and observe it retry with increasing delay before landing in the DLQ:
   `queuectl enqueue '{"command":"this_command_does_not_exist"}'`
4. Confirm it appears in `queuectl dlq list`.
5. Retry it: `queuectl dlq retry <job_id>`, and confirm it re-processes (and re-fails, if the command is still invalid).
6. Run `queuectl status` to verify the state counts match expectations.
7. With multiple workers running, enqueue several jobs at once and confirm via `queuectl list` that each was processed exactly once — no duplicate completions, no jobs stuck in `processing`.
8. Stop and restart the worker process; confirm `queuectl list` still shows all previously enqueued jobs (persistence across restarts).

---

# Project Structure

```
queuectl/
│
├── cli.py           # Typer CLI: enqueue, worker, status, list, dlq, config
├── config.py        # Runtime configuration (SQLite-backed, per-database-path)
├── db.py            # SQLite persistence layer, atomic claiming logic
├── models.py        # Job dataclass, JobState enum
├── worker.py         # process_one_job(), run_worker(), multiprocessing entrypoint
└── __init__.py

tests/
├── test_cli.py
├── test_db.py
├── test_models.py
├── test_worker.py
└── __init__.py
```

---

# Design Decisions

- SQLite chosen for zero-dependency, transactional persistence.
- Atomic `UPDATE ... RETURNING` claiming removes the read-then-write race condition entirely, rather than relying on an external lock.
- Runtime configuration lives in the same database as job data — one source of truth, correctly parameterized by `db_path` so tests and production data never cross-contaminate.
- Exponential backoff with a hard cap balances the spec's formula against real-world worker behavior.
- Dead jobs are isolated by state rather than a separate table, keeping the schema simple while still fully supporting DLQ operations.
- Multiple workers run as independent OS processes via `multiprocessing`, with graceful shutdown (finish current job, then exit) on `Ctrl+C`.

---

# Future Improvements

- Detached worker management with a real SIGTERM-based `worker stop` for background processes
- Job priorities
- Scheduled/delayed jobs (`run_at`)
- Execution timeout handling
- Job output logging (persisted stdout/stderr, currently only captured transiently)
- Metrics or execution stats
- Minimal web dashboard for monitoring
- REST API

---

# Demo

**Demo Video:**
https://drive.google.com/file/d/1vQs1kdf5wilD-aMgPD7isEUdRg2MEiVF/view?usp=sharing

---

# License

This project was developed as part of a Backend Developer Internship assignment.