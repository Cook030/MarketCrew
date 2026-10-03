# 1、项目介绍
## 当前文件知识库功能

前端表单为“网址 + 本次任务目标 + 可选材料”。上传的 DOCX、文本 PDF、UTF-8 MD、HTML/HTM
经正文提取和 LlamaIndex 切分、Embedding 后构建独立的项目索引。
三个 Agent 共享本次项目的检索工具，初始检索结果也会传入五个任务。
检索返回文件名、页码或章节、chunk_id 和正文，生成结果的 `sources` 用于引用依据。

### 安装和启动

```powershell
cd crewaiBackend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# 填写 .env 的模型和 Embedding 地址、模型名与 API Key 后启动
.\.venv\Scripts\python.exe -X utf8 main.py
```

Chat 和 Embedding 独立配置。`EMBEDDING_API_KEY` 为空时回退到 `OPENAI_API_KEY`；
Embedding 服务须支持 `/embeddings`。切换 Chat 到 OneAPI 或 Ollama 不会自动切换 Embedding。
修改 Embedding 模型或地址后须重建索引。`.env` 和知识库数据均被 Git 忽略。
首次建库会将提取的文本发送给所配置的 Embedding 服务；任务会将检索片段发送给所配置的 Chat 服务。

旧版 `crewai-tools` 的 LanceDB 依赖无法在本项目 Windows/Python 环境安装，
因此保留 CrewAI 0.55.2，使用它支持的 LangChain `StructuredTool` 提供项目检索、网页读取和 Serper 搜索。
未配置 `SERPER_API_KEY` 时不提供网页搜索工具，网页读取仍可使用。
Crew 和任务使用显式构造，固定顺序仍是研究、项目理解、营销战略、活动创意、文案。

### 接口

- `POST /api/knowledge-bases`：multipart 表单，`files` 字段可重复，上传 1 至 5 个文件，每个最多 10 MB；返回 202 和 `knowledge_base_id`。
- `GET /api/knowledge-bases/{id}`：返回 `PENDING / PROCESSING / READY / ERROR`、材料状态和片段数量。只有 READY 可启动带材料的任务。
- `POST /api/crew`：JSON 包含 `customer_domain`、`task_goal` 和可选 `knowledge_base_id`。旧版 `project_description` 仍可作为目标字段。
- `GET /api/crew/{job_id}`：返回任务状态、结果、事件、本次知识库 ID 和实际检索过的 `sources`。来源清单是检索记录，不保证所有片段均支持最终结论。

```json
{
  "customer_domain": "https://example.com",
  "task_goal": "为新品制定面向年轻通勤者的推广策略和社交媒体文案",
  "knowledge_base_id": "上传接口返回的 UUID"
}
```

知识库原文件、状态和索引保存于 `crewaiBackend/data/knowledge-bases/{id}`；可用 `DATA_DIRECTORY` 更改目录。
已完成的知识库可在重启后加载，处理中重启的知识库会标记失败，需重新上传。
执行中的任务、事件和结果仍保存在内存中，服务重启不恢复任务。
这是监听本机的单用户开发服务，尚未实现用户登录、租户权限、多进程任务队列、OCR 或 `.doc` 转换。
运行多个服务进程前应替换当前线程和文件状态管理；不要将本地 UUID 隔离理解为租户授权。

以下保留原教程说明；当前启动和配置方式以上述环境变量方案为准，原文中的示例凭据不用于运行。

本期视频主要实现使用Flask后端框架实现后端服务并使用ApiFox进行前后端联调            
业务流程图如下所示:        
<img src="./img.png" alt="业务流程图" width="900" />                     

# 2、前期准备工作 
## 2.1 CrewAI介绍
### (1)简介
CrewAI是一个用于构建多Agent系统的工具，它能够让多个具有不同角色和目标的Agent共同协作，完成复杂的Task                
该工具可以将Task分解，分配给不同的Agent，借助它们的特定技能和工具，完成各自的职责，最终实现整体任务目标              
官网:https://www.crewai.com/                                          
GitHub:https://github.com/crewAIInc/crewAI                                          
官方首页的介绍:                          
AI Agents for real use cases                                           
Most AI agent frameworks are hard to use.We provide power with simplicity.                                           
Automate your most important workflows quickly.            
### (2)核心概念
**Agents:**          
是一个自主可控单元，通过编程可以实现执行任务、作出决定、与其他Agent协作交流          
可类比为团队中的一员，拥有特定的技能和任务                    
属性:             
role(角色):定义Agent在团队中的角色功能                              
goal(目标):Agent实现的目标                             
backstory(背景信息):为Agent提供上下文                                    
**Tasks:**               
分配给Agent的具体任务，提供执行任务所需的所有细节                          
属性:                         
description(任务描述):简明扼要说明任务要求                                                 
agent(分配的Agent):分配负责该任务的Agent                                                
expected_output(期望输出):任务完成情况的详细描述                                                         
Tools(工具列表):为Agent提供可用于执行该任务的工具列表                   
output_json(输出json):输出一个json对象，只能输出一种数据格式                    
output_file(工具列表):将任务结果输出到一个文件中，指定输出的文件格式                                                     
context(上下文):指定其输出被用作该任务上下文的任务                                  
**Processes**                      
CrewAI中负责协调Agent执行任务                        
类似于团队中的项目经理                        
确保任务分配和执行效率与预定计划保持一致                       
目前拥有两种实施机制:                             
sequential(顺序流程):反映了crew中动态的工作流程，以深思熟虑的和系统化的方式推进各项任务，按照任务列表中预定义的顺序执行，一个任务的输出作为下一个任务的上下文            
hierarchical(分层流程):允许指定一个自定义的管理Agent，负责监督任务执行，包括计划、授权和验证。任务不是预先分配的，而是根据Agent的能力进行任务分配，审查产出并评估任务完成情况              
**Crews:**          
1个crew代表一组合作完成一系列任务的Agent                        
每个crew定义了任务执行策略、Agent协作和整体工作流程                                          
属性:                               
Tasks(任务列表):分配给crew的任务列表                                                          
Agents(Agent列表):分配给crew的Agent列表                                                         
Process(背景信息):crew遵循的流程                              
manager_llm(大模型):在hierarchical模式下指定大模型                                                                             
language(语言):指定crew使用的语言                                                                                               
language_file(语言文件):指定crew使用的语言文件                        
**Pipleline:**          
在CrewAI中,pipleline代表一种结构化的工作流程，允许多个crew顺序或并行执行           
提供了一种组织涉及多个阶段的复杂流程的方法，其中一个阶段的输出可作为后续阶段的输入                                                        
关键术语:                               
Stage:pipleline中的1个独立部分，可以是1个顺序crews，也可以是一个并行的crews                                                                       
Run:运行pipleling处理的单个实例                                                                    
Branch:Stage内的并行执行                                                      
Trace:单个输入在整个pipleline中的运行轨迹、捕捉它所经历的路径和转换            

## 2.2 anaconda、pycharm 安装   
anaconda:提供python虚拟环境，官网下载对应系统版本的安装包安装即可                                      
pycharm:提供集成开发环境，官网下载社区版本安装包安装即可                                               
可参考如下视频进行安装，【大模型应用开发基础】集成开发环境搭建Anaconda+PyCharm                                                          
https://www.bilibili.com/video/BV1q9HxeEEtT/?vd_source=30acb5331e4f5739ebbad50f7cc6b949                             
https://youtu.be/myVgyitFzrA                                           

## 2.3 GPT大模型使用方案            
可以使用代理的方式，具体代理方案自己选择                                   
可以参考视频《GraphRAG最新版本0.3.0对比实战评测-使用gpt-4o-mini和qwen-plus分别构建近2万字文本知识索引+本地/全局检索对比测试》中推荐的方式:                                    
https://www.bilibili.com/video/BV1maHxeYEB1/?vd_source=30acb5331e4f5739ebbad50f7cc6b949                                    
https://youtu.be/iXfsJrXCEwA                     

## 2.4 非GPT大模型(国产大模型)使用方案,OneAPI安装、部署、创建渠道和令牌 
### （1）OneAPI是什么
官方介绍：是OpenAI接口的管理、分发系统             
支持 Azure、Anthropic Claude、Google PaLM 2 & Gemini、智谱 ChatGLM、百度文心一言、讯飞星火认知、阿里通义千问、360 智脑以及腾讯混元             
### (2)安装、部署、创建渠道和令牌   
创建渠道：大模型类型(通义千问)、APIKey(通义千问申请的真实有效的APIKey)                 
创建令牌：创建OneAPI的APIKey，后续代码中直接调用此APIKey                
### (3)详细介绍可以观看这期视频 
【GraphRAG+阿里通义千问大模型】构建+检索全流程实操，打造基于知识图谱的本地知识库，本地搜索、全局搜索二合一          
https://www.bilibili.com/video/BV1yzHxeZEG5/?vd_source=30acb5331e4f5739ebbad50f7cc6b949            
https://youtu.be/w9CRDbafhPI              
     
## 2.5 本地开源大模型使用方案,Ollama          
### （1）Ollama是什么
Ollama是一个轻量级、跨平台的工具和库，专门为本地大语言模型(LLM)的部署和运行提供支持          
它旨在简化在本地环境中运行大模型的过程，不需要依赖云服务或外部API，使用户能够更好地掌控和使用大型模型                
### （2）Ollama安装、启动、下载大模型
安装Ollama，进入官网https://ollama.com下载对应系统版本直接安装即可                                      
启动Ollama，安装所需要使用的本地模型，执行指令进行安装即可，参考如下:                                              
ollama pull qwen2:latest                                                
ollama pull llama3.1:latest                                             
ollama pull gemma2:latest                                                
### (3)详细介绍可以观看这期视频                                                 
【GraphRAG+Ollama】本地开源大模型llama3.1与qwen2构建+检索全流程实操对比评测，打造基于知识图谱的本地知识库，本地搜索、全局搜索二合一               
https://www.bilibili.com/video/BV1mpH9eVES1/?vd_source=30acb5331e4f5739ebbad50f7cc6b949                                                
https://youtu.be/thNMan45lWA               

## 2.6 Apifox          
官网下载软件安装即可，进行接口调试                          
https://apifox.com/                


# 3、项目初始化
## 3.1 下载源码
GitHub或Gitee中下载工程文件到本地，下载地址如下：                
https://github.com/NanGePlus/CrewAIFullstackTest          
https://gitee.com/NanGePlus/CrewAIFullstackTest                 

## 3.2 构建项目
使用pycharm构建一个项目，为项目配置虚拟python环境               
项目名称：CrewAIFullstackTest                                   

## 3.3 将相关代码拷贝到项目工程中           
直接将下载的文件夹中的文件拷贝到新建的项目目录中               

## 3.4 安装项目依赖          
命令行终端中执行cd crewaiBackend 命令进入到该文件夹内，然后执行如下命令安装依赖包                                           
pip install -r requirements.txt            
每个软件包后面都指定了本次视频测试中固定的版本号           


# 4、项目测试          
### （1）运行main脚本启动API服务
在使用python main.py命令启动脚本前，需根据自己的实际情况调整相关配置参数:         
**openai模型相关配置 根据自己的实际情况进行调整**              
OPENAI_API_BASE = "https://api.wlai.vip/v1"            
OPENAI_CHAT_API_KEY = "sk-XmrIEFplNArLlYa0E8C5A7C5F82041FdBd923e9d115746D0"          
OPENAI_CHAT_MODEL = "gpt-4o-mini"           
**非gpt大模型相关配置(oneapi方案 通义千问为例) 根据自己的实际情况进行调整**              
ONEAPI_API_BASE = "http://139.224.72.218:3000/v1"            
ONEAPI_CHAT_API_KEY = "sk-0FxX9ncd0yXjTQF877Cc9dB6B2F44aD08d62805715821b85"               
ONEAPI_CHAT_MODEL = "qwen-max"               
**本地大模型相关配置(Ollama方案 llama3.1:latest为例) 根据自己的实际情况进行调整**             
OLLAMA_API_BASE = "http://localhost:11434/v1"                
OLLAMA_CHAT_API_KEY = "ollama"          
OLLAMA_CHAT_MODEL = "llama3.1:latest"             
**openai:调用gpt大模型;oneapi:调用非gpt大模型;ollama:调用本地大模型**              
LLM_TYPE = "openai"           
**API服务设置相关  根据自己的实际情况进行调整**              
PORT = 8012  # 服务访问的端口                

### （2）打开Apifox进行测试            
在Apifox中新建项目，将提供的crewaiBackend文件夹下的api.json接口文件导入            
然后，测试运行crew POST请求                
http://127.0.0.1:8012/api/crew                  
获取某次运行crew作业详情 GET请求                    
http://127.0.0.1:8012/api/crew/{jobId}        
请求体内容:              
{                 
    "customer_domain": "https://www.emqx.com/zh",                          
    "project_description": "EMQX是一种开源的分布式消息中间件，专注于处理物联网 (IoT) 场景下的大规模消息通信。它基于MQTT协议，能够实现高并发、低延迟的实时消息推送，支持设备之间、设备与服务器之间的双向通信。客户领域:分布式消息中间件解决方案,项目概述:创建一个全面的营销活动，以提高企业客户对 EMQX 服务的认识和采用。"                 
}       

### （3）使用Vue.js实现一个简单的前端页面与后端进行数据交互                   
(1)准备工作       
官网下载安装node.js、下载安装VSCode编辑器，官网链接如下:             
https://nodejs.org/zh-cn         
https://code.visualstudio.com/         
(2)创建一个文件夹vuetest,在VSCode中打开该文件夹，打开终端执行如下命令创建项目         
npm create vue@latest         
在选择项中，指定项目名称，自定义即可，这里设置为vue-crewai，其他选项根据自己选择进行设置，一般默认选项即可            
(3)初始化并运行项目        
npm install                           
npm run dev             
(4)引入UI框架      
链接地址:https://element-plus.org/zh-CN/guide/installation.html            
npm install element-plus     
在代码中按需导入，先执行如下命令安装相关依赖                    
npm install -D unplugin-vue-components unplugin-auto-import       
最后在vite.config.js中新增内容后重启服务即可            
(5)编写页面代码        
在初始项目基础上进行改写，页面布局交互、前后端数据交互(使用axios调用后端接口)         
https://www.axios-http.cn/         
安装axios     npm install axios          
新增一个组件crewaiTest.vue,代码见crewaiTest.vue文件          
(6)启动后端服务，前端页面进行测试             
测试数据如下:              
https://www.emqx.com/zh                   
EMQX是一种开源的分布式消息中间件，专注于处理物联网 (IoT) 场景下的大规模消息通信。它基于MQTT协议，能够实现高并发、低延迟的实时消息推送，支持设备之间、设备与服务器之间的双向通信。客户领域:分布式消息中间件解决方案,项目概述:创建一个全面的营销活动，以提高企业客户对 EMQX 服务的认识和采用。                  
