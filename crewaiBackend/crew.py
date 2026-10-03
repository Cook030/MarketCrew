from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task

from utils.agentTools import web_tools
from utils.jobManager import append_event
from utils.models import CampaignIdea, Copy, MarketStrategy


class CrewtestprojectCrew:
    def __init__(self, job_id, llm, knowledge_tool=None):
        self.job_id = job_id
        directory = Path(__file__).parent / 'config'
        agents_config = yaml.safe_load((directory / 'agents.yaml').read_text(encoding='utf-8'))
        tasks_config = yaml.safe_load((directory / 'tasks.yaml').read_text(encoding='utf-8'))
        material_tools = [knowledge_tool] if knowledge_tool else []
        agents = {}
        for name, config in agents_config.items():
            tools = list(material_tools)
            if name != 'creative_content_creator':
                tools.extend(web_tools())
            agents[name] = Agent(
                config=config, llm=llm, tools=tools, verbose=False,
                allow_delegation=False, max_iter=12, cache=False,
            )
        schemas = {
            'marketing_strategy_task': MarketStrategy,
            'campaign_idea_task': CampaignIdea,
            'copy_creation_task': Copy,
        }
        tasks = {}
        for name, config in tasks_config.items():
            config = dict(config)
            agent_name = config.pop('agent')
            options = {}
            if name in schemas:
                options['output_json'] = schemas[name]
            if name == 'copy_creation_task':
                options['context'] = [tasks['marketing_strategy_task'], tasks['campaign_idea_task']]
            tasks[name] = Task(
                config=config, agent=agents[agent_name],
                callback=self.append_event_callback, **options,
            )
        self._crew = Crew(
            agents=list(agents.values()), tasks=list(tasks.values()),
            process=Process.sequential, verbose=False, cache=False,
        )

    def append_event_callback(self, task_output):
        append_event(self.job_id, task_output.raw)

    def crew(self):
        return self._crew

    def kickoff(self, inputs):
        # Let failures reach the API worker, which owns the ERROR/COMPLETE transition.
        return self._crew.kickoff(inputs=inputs)
