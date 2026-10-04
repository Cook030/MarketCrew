"""Project-scoped document ingestion and persistent LlamaIndex retrieval."""

import json
import os
from pathlib import Path
from threading import Lock, Thread
from uuid import UUID, uuid4
from zipfile import ZipFile

from bs4 import BeautifulSoup
from docx import Document as WordDocument
from docx.table import Table
from llama_index.core import Document, StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from pypdf import PdfReader

MAX_FILES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARACTERS = 2_000_000
SUPPORTED_EXTENSIONS = {'.docx', '.pdf', '.md', '.html', '.htm'}


class KnowledgeBaseError(ValueError):
    """An actionable error safe to display to the user."""


def embedding_config():
    return {
        'model': os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small'),
        'api_base': os.getenv('EMBEDDING_API_BASE', 'https://api.openai.com/v1'),
    }


def create_embedding(config):
    key = os.getenv('EMBEDDING_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not key:
        raise KnowledgeBaseError('请先配置 EMBEDDING_API_KEY 或 OPENAI_API_KEY，再上传材料')
    return OpenAIEmbedding(
        model_name=config['model'], api_base=config['api_base'], api_key=key,
        timeout=30, max_retries=2, embed_batch_size=16,
    )


def parse_material(path, file):
    """Return text sections with honest locations; DOCX has no stable page numbers."""
    sections = []
    extension = path.suffix.lower()
    if extension == '.pdf':
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise KnowledgeBaseError(f"{file['filename']}：请上传未加密的 PDF")
        for number, page in enumerate(reader.pages, start=1):
            sections.append((f'第 {number} 页', page.extract_text() or ''))
    elif extension == '.docx':
        with ZipFile(path) as archive:
            if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
                raise KnowledgeBaseError(f"{file['filename']}：文档解压后过大")
        word = WordDocument(path)
        heading, lines = '正文', []
        for block in word.iter_inner_content():
            if isinstance(block, Table):
                lines.extend(' | '.join(cell.text for cell in row.cells) for row in block.rows)
            elif block.style and block.style.name.lower().startswith('heading'):
                if lines:
                    sections.append((heading, '\n'.join(lines)))
                heading, lines = block.text, [block.text]
            else:
                lines.append(block.text)
        sections.append((heading, '\n'.join(lines)))
    elif extension == '.md':
        try:
            text = path.read_text(encoding='utf-8-sig')
        except UnicodeError as exc:
            raise KnowledgeBaseError(f"{file['filename']}：请将 Markdown 保存为 UTF-8") from exc
        heading, lines, fenced = '正文', [], False
        for line in text.splitlines():
            if line.lstrip().startswith(('```', '~~~')):
                fenced = not fenced
            if not fenced and line.startswith('#') and line.lstrip('#').startswith(' '):
                if lines:
                    sections.append((heading, '\n'.join(lines)))
                heading, lines = line.lstrip('#').strip(), [line]
            else:
                lines.append(line)
        sections.append((heading, '\n'.join(lines)))
    else:
        soup = BeautifulSoup(path.read_bytes(), 'html.parser')
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'noscript']):
            element.decompose()
        title = soup.title.get_text(' ', strip=True) if soup.title else '正文'
        body = soup.find('main') or soup.find('article') or soup.body or soup
        sections.append((title, body.get_text('\n', strip=True)))

    documents = []
    for location, text in sections:
        if text.strip():
            documents.append(Document(
                text=text.strip(),
                metadata={'file_id': file['id'], 'filename': file['filename'], 'location': location},
                excluded_embed_metadata_keys=['file_id'],
                excluded_llm_metadata_keys=['file_id'],
            ))
    if not documents:
        raise KnowledgeBaseError(f"{file['filename']}：未提取到正文；扫描 PDF 需先进行文字识别")
    return documents


class KnowledgeBaseStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        # A worker cannot survive a process restart. Never leave a project 'processing' forever.
        for path in self.root.glob('*/manifest.json'):
            manifest = json.loads(path.read_text(encoding='utf-8'))
            if manifest['status'] in {'PENDING', 'PROCESSING'}:
                manifest.update(status='ERROR', message='处理过程中服务已重启，请重新上传材料')
                for file in manifest['files']:
                    file['status'] = 'ERROR'
                self._write(manifest)

    def _directory(self, knowledge_base_id):
        try:
            canonical = str(UUID(knowledge_base_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise KnowledgeBaseError('无效的知识库 ID') from exc
        if canonical != knowledge_base_id:
            raise KnowledgeBaseError('无效的知识库 ID')
        return self.root / canonical

    def _write(self, manifest):
        directory = self._directory(manifest['knowledge_base_id'])
        with self.lock:
            temporary = directory / 'manifest.tmp'
            temporary.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
            temporary.replace(directory / 'manifest.json')

    def get(self, knowledge_base_id):
        path = self._directory(knowledge_base_id) / 'manifest.json'
        if not path.is_file():
            raise FileNotFoundError('知识库不存在')
        return json.loads(path.read_text(encoding='utf-8'))

    def create(self, uploads):
        if not 1 <= len(uploads) <= MAX_FILES:
            raise KnowledgeBaseError('请上传 1 至 5 个材料文件')
        validated = []
        for upload in uploads:
            filename = Path((upload.filename or '').replace('\\', '/')).name
            extension = Path(filename).suffix.lower()
            if extension not in SUPPORTED_EXTENSIONS:
                raise KnowledgeBaseError('仅支持 DOCX、PDF、MD、HTML 文件')
            content = upload.stream.read(MAX_FILE_BYTES + 1)
            if not content or len(content) > MAX_FILE_BYTES:
                raise KnowledgeBaseError(f'{filename}：文件须非空且不得超过 10 MB')
            file_id = str(uuid4())
            validated.append(({
                'id': file_id, 'filename': filename, 'stored_name': file_id + extension,
                'size': len(content), 'status': 'PENDING',
            }, content))

        # Validate provider configuration before accepting a job that cannot build an index.
        config = embedding_config()
        create_embedding(config)
        knowledge_base_id = str(uuid4())
        directory = self._directory(knowledge_base_id)
        (directory / 'files').mkdir(parents=True)
        for file, content in validated:
            (directory / 'files' / file['stored_name']).write_bytes(content)
        manifest = {
            'knowledge_base_id': knowledge_base_id, 'status': 'PENDING',
            'message': '材料已上传，等待解析', 'files': [file for file, _ in validated],
            'embedding': config, 'chunk_count': 0,
        }
        self._write(manifest)
        # ponytail: one local worker per upload; use a bounded queue for concurrent users.
        Thread(target=self._build, args=(knowledge_base_id,), daemon=True).start()
        return manifest

    def _build(self, knowledge_base_id):
        manifest = self.get(knowledge_base_id)
        directory = self._directory(knowledge_base_id)
        try:
            manifest.update(status='PROCESSING', message='正在解析材料')
            self._write(manifest)
            documents = []
            for file in manifest['files']:
                file['status'] = 'PROCESSING'
                self._write(manifest)
                try:
                    documents.extend(parse_material(directory / 'files' / file['stored_name'], file))
                except KnowledgeBaseError:
                    raise
                except Exception as exc:
                    raise KnowledgeBaseError(f"{file['filename']}：解析失败，请检查文件是否损坏或格式不符") from exc
                if sum(len(doc.text) for doc in documents) > MAX_TEXT_CHARACTERS:
                    raise KnowledgeBaseError('材料正文总量过大，请拆分项目后上传')
                file['status'] = 'PARSED'
                self._write(manifest)

            manifest['message'] = '正在切分正文并建立索引'
            self._write(manifest)
            nodes = SentenceSplitter(chunk_size=512, chunk_overlap=64).get_nodes_from_documents(documents)
            for node in nodes:
                node.metadata['chunk_id'] = node.node_id
                node.excluded_embed_metadata_keys.append('chunk_id')
            index = VectorStoreIndex(nodes, embed_model=create_embedding(manifest['embedding']))
            index.storage_context.persist(persist_dir=str(directory / 'index'))
            for file in manifest['files']:
                file['status'] = 'READY'
            manifest.update(status='READY', message='知识库已就绪', chunk_count=len(nodes))
        except Exception as exc:
            for file in manifest['files']:
                file['status'] = 'ERROR'
            message = str(exc) if isinstance(exc, KnowledgeBaseError) else '索引建立失败，请检查 Embedding 服务配置和连接后重新上传'
            manifest.update(status='ERROR', message=message)
        self._write(manifest)

    def retriever(self, knowledge_base_id):
        manifest = self.get(knowledge_base_id)
        if manifest['status'] != 'READY':
            raise KnowledgeBaseError('知识库尚未就绪，请完成材料处理后再启动')
        if manifest['embedding'] != embedding_config():
            raise KnowledgeBaseError('Embedding 模型或服务地址已更改，请重新建立知识库')
        storage = StorageContext.from_defaults(persist_dir=str(self._directory(knowledge_base_id) / 'index'))
        index = load_index_from_storage(storage, embed_model=create_embedding(manifest['embedding']))
        return index.as_retriever(similarity_top_k=5)


def retrieve_passages(retriever, query):
    if not isinstance(query, str) or not query.strip() or len(query) > 4000:
        raise KnowledgeBaseError('检索问题须为 1 至 4000 个字符')
    passages = []
    for match in retriever.retrieve(query.strip()):
        if match.score is not None and match.score <= 0:
            continue
        metadata = match.node.metadata
        passages.append({
            'filename': metadata['filename'], 'location': metadata['location'],
            'chunk_id': match.node.node_id, 'text': match.node.text, 'score': match.score,
        })
    return passages
