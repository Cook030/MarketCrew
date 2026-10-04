import os
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

load_dotenv(Path(__file__).with_name('.env'))
data_directory = Path(os.getenv('DATA_DIRECTORY', str(Path(__file__).parent / 'data'))).resolve()
# A transitive CrewAI dependency creates a cache on import; keep it inside project data.
os.environ.setdefault('MEM0_DIR', str(data_directory / 'mem0'))
os.environ.setdefault('EMBEDCHAIN_CONFIG_DIR', str(data_directory))
os.environ.setdefault('CREWAI_STORAGE_DIR', str(data_directory / 'crew-memory'))

from utils.jobManager import Job, append_event, jobs, jobs_lock, record_sources, set_phase
from utils.knowledgeBase import KnowledgeBaseError, KnowledgeBaseStore, embedding_config

PORT = int(os.getenv('PORT', '8012'))
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 51 * 1024 * 1024
CORS(app, resources={r'/api/*': {'origins': ['http://localhost:5173', 'http://127.0.0.1:5173']}})
knowledge_bases = KnowledgeBaseStore(data_directory / 'knowledge-bases')


@app.errorhandler(HTTPException)
def http_error(error):
    message = '请求体过大，最多上传 5 个文件，每个不超过 10 MB' if error.code == 413 else error.description
    return jsonify(message=message), error.code


@app.errorhandler(KnowledgeBaseError)
def knowledge_error(error):
    return jsonify(message=str(error)), 400


@app.errorhandler(FileNotFoundError)
def missing_knowledge_base(_error):
    return jsonify(message='知识库不存在'), 404


@app.post('/api/knowledge-bases')
def upload_materials():
    if set(request.files) - {'files'}:
        return jsonify(message='请使用 files 字段上传材料'), 400
    manifest = knowledge_bases.create(request.files.getlist('files'))
    return jsonify(manifest), 202


@app.get('/api/knowledge-bases/<knowledge_base_id>')
def knowledge_status(knowledge_base_id):
    return jsonify(knowledge_bases.get(knowledge_base_id))


def kickoff_crew(job_id, inputs, knowledge_base_id=None):
    try:
        from crew import CrewtestprojectCrew
        from utils.agentTools import make_knowledge_tool
        from utils.myLLM import my_llm

        set_phase(job_id, 'Thinking')
        tool = None
        inputs = dict(inputs)
        if knowledge_base_id:
            append_event(job_id, '正在加载本次项目知识库')
            tool = make_knowledge_tool(
                knowledge_bases, knowledge_base_id,
                lambda passages: record_sources(job_id, passages), job_id=job_id,
            )
            # Initial retrieval ensures uploaded material reaches the workflow even before a tool call.
            set_phase(job_id, 'Searching')
            inputs['knowledge_context'] = tool.invoke({'query': inputs['project_description']})
        else:
            inputs['knowledge_context'] = '未提供项目材料。不可虚构材料事实；可通过网址收集公开信息。'
        set_phase(job_id, 'Thinking')
        append_event(job_id, '开始执行营销任务')
        output = CrewtestprojectCrew(job_id, my_llm(os.getenv('LLM_TYPE', 'openai')), tool).kickoff(inputs)
        result = output.json_dict if output.json_dict is not None else output.raw
        with jobs_lock:
            jobs[job_id].status = 'COMPLETE'
            jobs[job_id].phase = 'Finished'
            jobs[job_id].result = result
        append_event(job_id, '任务完成')
    except Exception as error:
        # Provider exception strings can contain request content or credentials. Do not send them to the UI.
        app.logger.error('Job %s failed (%s)', job_id, type(error).__name__)
        message = str(error) if isinstance(error, KnowledgeBaseError) else '任务执行失败，请检查模型、Embedding 或网页服务配置后重试'
        with jobs_lock:
            jobs[job_id].status = 'ERROR'
            jobs[job_id].phase = 'Failed'
            jobs[job_id].result = None
        append_event(job_id, message)


@app.post('/api/crew')
def run_crew():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(message='请提交 JSON 格式的任务信息'), 400
    domain = data.get('customer_domain')
    goal = data.get('task_goal', data.get('project_description'))
    if not isinstance(domain, str) or not isinstance(goal, str) or not goal.strip():
        return jsonify(message='网址和本次任务目标均为必填'), 400
    try:
        parsed_url = urlsplit(domain.strip())
        if parsed_url.scheme not in {'http', 'https'} or not parsed_url.hostname:
            raise ValueError('Invalid URL')
    except ValueError:
        return jsonify(message='请输入有效的 HTTP 或 HTTPS 网址'), 400
    if len(goal.strip()) > 4000:
        return jsonify(message='本次任务目标不得超过 4000 个字符'), 400
    knowledge_base_id = data.get('knowledge_base_id')
    if knowledge_base_id is not None:
        manifest = knowledge_bases.get(knowledge_base_id)
        if manifest['status'] != 'READY':
            return jsonify(message='知识库尚未就绪，请等待处理完成或重新上传'), 409
        if manifest['embedding'] != embedding_config():
            return jsonify(message='Embedding 配置已更改，请重新建立知识库'), 409
    inputs = {'customer_domain': domain.strip(), 'project_description': goal.strip()}
    job_id = str(uuid4())
    # Publish the job before starting the thread; immediate polling must not return 404.
    with jobs_lock:
        jobs[job_id] = Job(knowledge_base_id=knowledge_base_id)
    append_event(job_id, '任务已提交')
    Thread(target=kickoff_crew, args=(job_id, inputs, knowledge_base_id), daemon=True).start()
    return jsonify(job_id=job_id), 202


@app.get('/api/crew/<job_id>')
def get_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return jsonify(message='任务不存在'), 404
        # Snapshot mutable state under the lock before serializing.
        return jsonify(
            job_id=job_id, status=job.status, phase=job.phase, result=job.result,
            knowledge_base_id=job.knowledge_base_id, sources=list(job.sources),
            events=[{'timestamp': event.timestamp.isoformat(), 'data': event.data} for event in job.events],
        )


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=PORT)
