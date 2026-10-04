"""Run with .venv/Scripts/python.exe -X utf8 check_progress.py; no network calls."""
from utils.jobManager import Job, jobs
from utils import agentTools

job_id = 'progress-check'
jobs[job_id] = Job()
original = agentTools.read_website

def fake_read(url: str) -> str:
    """Read a test page."""
    assert jobs[job_id].phase == 'Searching'
    if url.endswith('/fail'):
        raise RuntimeError('expected test failure')
    return 'sample page'

try:
    assert jobs[job_id].phase == 'Starting'
    agentTools.read_website = fake_read
    tool = agentTools.web_tools(job_id)[0]
    assert tool.invoke({'url': 'https://example.com'}) == 'sample page'
    assert jobs[job_id].phase == 'Thinking'
    try:
        tool.invoke({'url': 'https://example.com/fail'})
        raise AssertionError('Expected tool failure')
    except RuntimeError:
        assert jobs[job_id].phase == 'Thinking'
finally:
    agentTools.read_website = original
    jobs.pop(job_id)
print('Progress transitions PASS')
