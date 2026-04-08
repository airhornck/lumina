"""
Intent API 路由

暴露 Intent Engine 的 HTTP 接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/intent", tags=["intent"])


class IntentRequest(BaseModel):
    text: str
    user_id: str
    session_context: Optional[Dict[str, Any]] = None


class IntentResponse(BaseModel):
    intent_type: str
    subtype: Optional[str]
    confidence: float
    requires_clarification: bool
    questions: Optional[list]
    suggestions: Optional[list]


@router.post("/recognize", response_model=IntentResponse)
async def recognize_intent(request: IntentRequest):
    """
    识别用户意图
    
    四级架构：L1规则 -> L2记忆 -> L2.5分类器 -> L3 LLM
    """
    try:
        # 延迟导入避免循环依赖
        from intent.engine import IntentEngine
        
        engine = IntentEngine()
        result = await engine.recognize(
            text=request.text,
            user_id=request.user_id,
            session_context=request.session_context or {}
        )
        
        return IntentResponse(
            intent_type=result.type.value,
            subtype=result.subtype,
            confidence=result.confidence,
            requires_clarification=result.requires_clarification,
            questions=result.clarification_questions or None,
            suggestions=result.clarification_options or None
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clarify")
async def handle_clarification(
    user_response: str,
    original_text: str,
    possible_intents: list,
    user_id: str
):
    """
    处理澄清响应
    """
    from intent.engine import IntentEngine
    
    engine = IntentEngine()
    result = await engine.handle_clarification_response(
        user_response=user_response,
        original_text=original_text,
        possible_intents=possible_intents,
        user_id=user_id
    )
    
    return {
        "intent_type": result.type.value,
        "subtype": result.subtype,
        "confidence": result.confidence
    }
