from queuectl.models import Job, JobState


def test_new_job_defaults():
    job = Job(id="job1", command="echo Hello")

    assert job.id == "job1"
    assert job.command == "echo Hello"
    assert job.state == JobState.PENDING
    assert job.attempts == 0
    assert job.max_retries == 3


def test_timestamps_are_created():
    job = Job(id="job1", command="echo Hello")

    assert job.created_at is not None
    assert job.updated_at is not None


def test_next_run_at_is_none():
    job = Job(id="job1", command="echo Hello")

    assert job.next_run_at is None