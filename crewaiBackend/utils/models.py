# 核心功能:定义数据模型，使用Pydantic库来进行数据验证和类型检查


from typing import List
from pydantic import BaseModel, Field

class MarketStrategy(BaseModel):
	"""Market strategy model"""
	name: str = Field(..., description="市场战略名称")
	tatics: List[str] = Field(..., description="市场战略中使用的战术清单")
	channels: List[str] = Field(..., description="市场战略中使用的渠道清单")
	KPIs: List[str] = Field(..., description="市场战略中使用的关键绩效指标清单")
	sources: List[str] = Field(default_factory=list, description="支持结论的材料引用：文件名、位置、chunk_id；公开资料引用 URL")

class CampaignIdea(BaseModel):
	"""Campaign idea model"""
	name: str = Field(..., description="活动创意名称")
	description: str = Field(..., description="Description of the campaign idea")
	audience: str = Field(..., description="活动创意说明")
	channel: str = Field(..., description="活动创意渠道")
	sources: List[str] = Field(default_factory=list, description="支持创意的材料引用：文件名、位置、chunk_id")

class Copy(BaseModel):
	"""Copy model"""
	title: str = Field(..., description="副本标题")
	body: str = Field(..., description="正文")
	sources: List[str] = Field(default_factory=list, description="支持文案事实的材料引用：文件名、位置、chunk_id")
