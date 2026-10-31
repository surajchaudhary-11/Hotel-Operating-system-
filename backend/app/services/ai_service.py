"""
HotelOS — AI Hotel Operations & General Knowledge Assistant Orchestrator
Production-ready conversational engine with configurable LLM providers (Google Gemini / OpenAI),
bimodal execution (General Knowledge Mode vs. Hotel Operations Mode),
strict human-in-the-loop action confirmation, role-based access control (RBAC),
multi-tenant isolation, PII masking, USALI financial compliance, and zero-key fallback.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import TenantContext
from app.models.models import (
    AssistantConversation, AssistantMessage, AssistantToolLog
)
from app.schemas.schemas import ActionProposal
from app.services.ai_tools import AVAILABLE_AI_TOOLS

logger = logging.getLogger("hotelos.ai")

# =====================================================================
# OPENAPI / FUNCTION SPECIFICATIONS FOR HOTEL OPERATIONS TOOLS
# =====================================================================

LLM_TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_room_status",
            "description": "Get current status, floor, room type, and occupancy of all rooms or a specific room.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_number": {"type": "string", "description": "Optional room number (e.g. '101')"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_vacant_rooms",
            "description": "List all vacant rooms (clean ready to sell and dirty awaiting cleaning).",
            "parameters": {
                "type": "object",
                "properties": {
                    "clean_only": {"type": "boolean", "description": "True to only return vacant clean rooms"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_occupied_rooms",
            "description": "List all currently occupied rooms with stay information and guest names.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_rooms_under_maintenance",
            "description": "List rooms currently blocked or undergoing maintenance.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_rooms_by_floor",
            "description": "Get all rooms situated on a specific floor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "floor_number": {"type": "integer", "description": "Floor number (e.g. 1, 2, 3)"}
                },
                "required": ["floor_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_bookings",
            "description": "Get today's scheduled check-ins, check-outs, and active guest stays.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_checkins",
            "description": "List today's scheduled or completed guest check-ins.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_checkouts",
            "description": "List today's scheduled departures and guest check-outs.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_reservations",
            "description": "List upcoming guest reservations over the next N days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days ahead (default 7)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_rooms_needing_cleaning",
            "description": "List all dirty rooms waiting for housekeeping turnover.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_housekeeping_tasks",
            "description": "List all pending or in-progress cleaning tasks, priorities, and assigned attendants.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_staff_pending_tasks",
            "description": "Show cleaning task workload broken down by housekeeping staff member.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_housekeeping_summary",
            "description": "Summary of clean, dirty, and inspection-pending rooms across the property.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_room_cleaning_status",
            "description": "Check cleaning status and checklist for a specific room number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_number": {"type": "string", "description": "Room number (e.g. '101')"}
                },
                "required": ["room_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_maintenance_requests",
            "description": "List all open maintenance tickets, issue titles, priority levels, and assigned technicians.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_rooms_with_unresolved_maintenance",
            "description": "List rooms that currently have unresolved maintenance issues.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_maintenance_summary",
            "description": "Overview of open maintenance tickets and blocked rooms.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_low_stock_items",
            "description": "List linens, toiletries, or assets that have fallen below minimum reorder thresholds.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_quantities",
            "description": "Show current quantities of linens and toiletries across storage and rooms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Optional category filter ('Linen', 'Consumable')"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_summary",
            "description": "High-level summary of total asset valuations and low-stock categories.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_revenue_summary",
            "description": "USALI 11th Edition revenue summary: earned accrual revenue, cash collections, and operating contribution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string", "description": "'today', 'yesterday', or 'month'"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_outstanding_balances",
            "description": "List in-house guest stays with unpaid folio balances.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_housekeeping_task",
            "description": "Propose creating a housekeeping cleaning task for a room.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_number": {"type": "string", "description": "Room number"},
                    "priority": {"type": "string", "description": "LOW, MEDIUM, HIGH, CRITICAL"},
                    "notes": {"type": "string", "description": "Special cleaning notes"}
                },
                "required": ["room_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_maintenance_ticket",
            "description": "Propose creating a maintenance repair ticket for an issue in a room.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_number": {"type": "string", "description": "Room number"},
                    "title": {"type": "string", "description": "Brief problem title"},
                    "description": {"type": "string", "description": "Detailed defect description"},
                    "priority": {"type": "string", "description": "LOW, MEDIUM, HIGH, CRITICAL"}
                },
                "required": ["room_number", "title", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assign_housekeeping_task",
            "description": "Propose assigning an existing cleaning task to a staff member.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Housekeeping task UUID"},
                    "staff_email_or_name": {"type": "string", "description": "Staff member name or email"}
                },
                "required": ["task_id", "staff_email_or_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task_status",
            "description": "Propose updating the status of a housekeeping task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Housekeeping task UUID"},
                    "new_status": {"type": "string", "description": "PENDING, IN_PROGRESS, INSPECTION_PENDING, READY, CANCELLED"}
                },
                "required": ["task_id", "new_status"]
            }
        }
    }
]

CONSEQUENTIAL_ACTIONS = {
    "create_housekeeping_task",
    "create_maintenance_ticket",
    "assign_housekeeping_task",
    "update_task_status"
}


class AIHotelAssistantService:

    # =================================================================
    # INTENT CLASSIFICATION & ROUTING
    # =================================================================

    @classmethod
    def classify_intent(cls, query: str) -> str:
        """
        Classifies user query into one of:
        - 'HOTEL_ANALOGY': Conceptual questions asking for a hotel analogy (e.g. 'Explain loops using a hotel example').
        - 'HOTEL_ACTION': State modifications (create task, log ticket, assign task).
        - 'HOTEL_DATA': Live hotel facts (rooms, vacancy, check-ins, check-outs, bookings, housekeeping, maintenance, revenue).
        - 'GENERAL_KNOWLEDGE': Programming (loops, functions, variables), technology, science, definitions, general Q&A.
        - 'AMBIGUOUS': Extremely short or vague queries requiring clarification.
        """
        q = query.lower().strip()

        # 1. Conceptual queries asking for a hotel analogy/example
        # These are GENERAL KNOWLEDGE questions and MUST NOT query the private hotel database!
        analogy_phrases = [
            "hotel example", "hotel analogy", "hotel scenario", "hotel theme",
            "using a hotel", "with a hotel", "like a hotel", "hotel ke udaharan",
            "होटल का उदाहरण", "होटल के उदाहरण", "होटल का एनालॉजी"
        ]
        if any(p in q for p in analogy_phrases) and any(w in q for w in [
            "explain", "what is", "how", "tell", "describe", "understand", "samjhao", "बताओ", "समझाओ"
        ]):
            return "HOTEL_ANALOGY"

        # 2. Consequential Actions (Hotel Modifications)
        action_verbs = ["create", "log", "ticket", "book", "assign", "schedule", "लॉग", "बनाओ", "दर्ज", "शुरू", "भेजो"]
        if any(w in q for w in ["repair", "fix", "broken", "leak", "खराब", "मरम्मत", "समस्या"]) and any(w in q for w in action_verbs):
            return "HOTEL_ACTION"
        if any(w in q for w in ["clean", "housekeep", "sweep", "mop", "सफाई", "क्लीनिंग"]) and any(w in q for w in ["create", "task", "बनाओ", "शुरू", "भेजो"]):
            return "HOTEL_ACTION"
        if "assign" in q and any(w in q for w in ["housekeep", "task", "clean", "सफाई", "टास्क"]):
            return "HOTEL_ACTION"
        if "update" in q and "task" in q:
            return "HOTEL_ACTION"

        # 3. Live Hotel Operational Queries
        hindi_hotel_tokens = [
            "कमरा", "कमरे", "खाली", "उपलब्ध", "भरे", "चेक-इन", "चेक-आउट",
            "सफाई", "हाउसकीपिंग", "मरम्मत", "स्टॉक", "रेवेन्यू", "खर्चा", "बकाया",
            "बुकिंग", "आरक्षण", "अतिथि", "मेहमान"
        ]
        if any(tok in q for tok in hindi_hotel_tokens):
            return "HOTEL_DATA"

        hotel_data_patterns = [
            r'\brooms?\b', r'room\s*\d{1,4}',
            r'\bvacan', r'\boccup',
            r'\bcheck-?\s*ins?\b', r'\bcheck-?\s*outs?\b',
            r'\bbookings?\b', r'\breservations?\b',
            r'\barrivals?\b', r'\bdepartures?\b',
            r'\bguests?\b',
            r'\bhousekeep', r'\bclean(?:ing)?\b', r'\bdirty\b',
            r'\bmaintenance\b', r'\brepairs?\b',
            r'\binventor', r'\bstocks?\b', r'\blinens?\b', r'\btowels?\b', r'\btoiletries\b',
            r'\brevenue\b', r'\bexpenses?\b', r'\bcollections?\b', r'\boperating contribution\b',
            r'\boutstanding', r'\bbalance due\b', r'\bfolios?\b', r'\bnight audit\b',
            r'\badr\b', r'\brevpar\b', r'\bfront desk\b', r'\bhousekeeper'
        ]
        if any(re.search(pat, q) for pat in hotel_data_patterns):
            return "HOTEL_DATA"

        # 4. General Knowledge Indicators
        general_indicators = [
            "loop", "function", "variable", "class", "object", "array", "list", "dict", "tuple",
            "python", "javascript", "typescript", "react", "fastapi", "sql", "git", "api", "rest",
            "recursion", "algorithm", "complexity", "database", "docker", "frontend", "backend",
            "math", "calculate", "solve", "what is", "explain", "how do", "how does", "define",
            "difference between", "tell me about", "why is", "who is", "who was", "capital of",
            "लूप", "फंक्शन", "पायथन"
        ]
        if any(w in q for w in general_indicators):
            return "GENERAL_KNOWLEDGE"

        # 5. Casual greetings & conversational
        if q in ["hi", "hello", "hey", "नमस्ते", "namaste", "good morning", "good evening", "how are you", "who are you"]:
            return "GENERAL_KNOWLEDGE"

        # 6. Ambiguous short query
        if len(q.split()) <= 1 and q in ["status", "check", "report", "show", "help"]:
            return "AMBIGUOUS"

        # Default fallback is General Knowledge to avoid incorrectly blocking benign questions
        return "GENERAL_KNOWLEDGE"

    # =================================================================
    # PRIMARY CONVERSATIONAL ENTRYPOINT
    # =================================================================

    @classmethod
    async def process_user_query(
        cls,
        db: AsyncSession,
        ctx: TenantContext,
        message_text: str,
        conversation_id: Optional[str] = None,
        confirm_action_id: Optional[str] = None,
        action_name: Optional[str] = None,
        action_parameters: Optional[Dict[str, Any]] = None,
        cancel_action_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for AI Assistant.
        Supports both General Knowledge Mode and Hotel Operations Mode.
        Enforces tenant context, role authorization, human-in-the-loop action confirmation,
        configurable LLM integration, and deterministic fallback.
        """
        start_time = datetime.now()
        hotel_id = ctx.hotel_id
        user_id = ctx.user.id
        cleaned_text = message_text.strip()
        is_hindi = cls._detect_hindi(cleaned_text)

        # 1. Resolve or create conversation with strict ownership check
        if conversation_id:
            res_conv = await db.execute(
                select(AssistantConversation).where(
                    AssistantConversation.id == conversation_id,
                    AssistantConversation.hotel_id == hotel_id,
                    AssistantConversation.user_id == user_id
                )
            )
            conv = res_conv.scalar_one_or_none()
            if not conv:
                conversation_id = None

        if not conversation_id:
            title_text = cleaned_text[:40] + ("..." if len(cleaned_text) > 40 else "")
            conv = AssistantConversation(
                hotel_id=hotel_id,
                user_id=user_id,
                title=title_text or "Hotel Assistant Query"
            )
            db.add(conv)
            await db.flush()
            conversation_id = conv.id

        # 2. Record User Message
        user_msg = AssistantMessage(
            conversation_id=conversation_id,
            sender="USER",
            content=cleaned_text
        )
        db.add(user_msg)
        await db.flush()

        # 3. Retrieve recent conversation history
        res_history = await db.execute(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conversation_id)
            .order_by(AssistantMessage.created_at.asc())
        )
        history_msgs = res_history.scalars().all()

        # 4. Handle Human-in-the-Loop Explicit Confirmation or Cancellation
        # Check if there is a pending proposal in recent messages
        has_pending_proposal = False
        pending_act_id = None
        pending_act_name = None
        pending_act_params = {}

        for past_m in reversed(history_msgs[:-1]):
            if past_m.tool_calls and isinstance(past_m.tool_calls, list):
                for tc in past_m.tool_calls:
                    if isinstance(tc, dict) and tc.get("type") == "action_proposal":
                        has_pending_proposal = True
                        pending_act_id = tc.get("action_id")
                        pending_act_name = tc.get("action_name")
                        pending_act_params = tc.get("parameters", {})
                        break
            if has_pending_proposal:
                break

        # A) Explicit Cancel
        is_verbal_cancel = cleaned_text.lower() in ["cancel", "abort", "रद्द", "रद्द करो"] or (
            cleaned_text.lower() in ["no", "नहीं"] and has_pending_proposal
        )

        if cancel_action_id or is_verbal_cancel:
            cancel_msg = "The action has been cancelled. No changes have been made to hotel records." if not is_hindi else "कार्रवाई रद्द कर दी गई है। होटल के रिकॉर्ड में कोई बदलाव नहीं किया गया है।"
            proposal = ActionProposal(
                action_id=cancel_action_id or pending_act_id or "cancelled",
                action_name=action_name or pending_act_name or "cancelled_action",
                title="Cancelled Action",
                parameters={},
                impact_summary="Action was cancelled by user.",
                status="cancelled"
            )
            asst_msg = AssistantMessage(
                conversation_id=conversation_id,
                sender="ASSISTANT",
                content=cancel_msg,
                tool_calls=["action_cancelled"]
            )
            db.add(asst_msg)
            await db.commit()
            return {
                "conversation_id": conversation_id,
                "message": cancel_msg,
                "tools_executed": ["action_cancelled"],
                "action_proposal": proposal,
                "action_executed": None,
                "timestamp": datetime.now(timezone.utc)
            }

        # B) Explicit Confirmation
        is_verbal_confirm = cleaned_text.lower() in [
            "confirm", "yes", "proceed", "yes, confirm", "execute", "confirm action",
            "कन्फर्म", "हाँ", "हाँ कन्फर्म करो", "स्वीकार", "करो"
        ] and has_pending_proposal

        if confirm_action_id or is_verbal_confirm:
            act_id = confirm_action_id or pending_act_id
            act_name = action_name or pending_act_name
            act_params = action_parameters or pending_act_params or {}

            if act_name and act_name in AVAILABLE_AI_TOOLS:
                # Duplicate prevention check
                res_dup = await db.execute(
                    select(AssistantToolLog).where(
                        AssistantToolLog.hotel_id == hotel_id,
                        AssistantToolLog.tool_name == f"executed_{act_name}_{act_id}"
                    )
                )
                if res_dup.scalar_one_or_none():
                    msg = "This action has already been executed. Duplicate execution was prevented." if not is_hindi else "यह कार्रवाई पहले ही निष्पादित की जा चुकी है। दोबारा करने से रोका गया।"
                    return {
                        "conversation_id": conversation_id,
                        "message": msg,
                        "tools_executed": [],
                        "action_proposal": None,
                        "action_executed": None,
                        "timestamp": datetime.now(timezone.utc)
                    }

                # Execute confirmed action
                tool_fn = AVAILABLE_AI_TOOLS[act_name]
                exec_res = await tool_fn(db=db, ctx=ctx, **act_params)

                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                tool_log = AssistantToolLog(
                    hotel_id=hotel_id,
                    user_id=user_id,
                    tool_name=f"executed_{act_name}_{act_id}",
                    parameters_json=act_params,
                    result_summary=str(exec_res.get("message", "Executed"))[:250],
                    execution_duration_ms=duration_ms
                )
                db.add(tool_log)

                proposal_executed = ActionProposal(
                    action_id=act_id or "act_done",
                    action_name=act_name,
                    title=f"Executed: {act_name.replace('_', ' ').title()}",
                    parameters=act_params,
                    impact_summary="Action successfully executed.",
                    status="executed"
                )

                ans_text = exec_res.get("message", "Action successfully executed.")
                if is_hindi:
                    ans_text = f"कार्रवाई सफलतापूर्वक पूरी हुई: {ans_text}"

                asst_msg = AssistantMessage(
                    conversation_id=conversation_id,
                    sender="ASSISTANT",
                    content=ans_text,
                    tool_calls=[act_name]
                )
                db.add(asst_msg)
                await db.commit()

                return {
                    "conversation_id": conversation_id,
                    "message": ans_text,
                    "tools_executed": [act_name],
                    "action_proposal": proposal_executed,
                    "action_executed": {"action_id": act_id, "action_name": act_name, "result": exec_res},
                    "timestamp": datetime.now(timezone.utc)
                }

        # 5. Classify Intent
        intent = cls.classify_intent(cleaned_text)
        logger.info(f"Classified intent: {intent} for query: {cleaned_text}")

        # Ambiguous Handling
        if intent == "AMBIGUOUS":
            clarify_msg = (
                "I can assist you with both **General Knowledge** (programming concepts, algorithms, general questions) "
                "and **Hotel Operations** (room occupancy, bookings, housekeeping, revenue, maintenance).\n\n"
                "Could you please specify what information or hotel task you would like help with?"
            ) if not is_hindi else (
                "मैं **सामान्य ज्ञान** (प्रोग्रामिंग, तकनीक, गणित) और **होटल ऑपरेशन्स** (कमरे, बुकिंग, सफाई, रेवेन्यू) दोनों में सहायता कर सकता हूँ।\n\n"
                "कृपया स्पष्ट करें कि आप किस विषय या होटल कार्य के बारे में जानना चाहते हैं?"
            )
            asst_msg = AssistantMessage(
                conversation_id=conversation_id,
                sender="ASSISTANT",
                content=clarify_msg,
                tool_calls=[]
            )
            db.add(asst_msg)
            await db.commit()
            return {
                "conversation_id": conversation_id,
                "message": clarify_msg,
                "tools_executed": [],
                "action_proposal": None,
                "action_executed": None,
                "timestamp": datetime.now(timezone.utc)
            }

        # 6. Execute via Selected Provider
        response_text = ""
        tools_executed: List[str] = []
        action_proposal: Optional[ActionProposal] = None

        provider = settings.AI_PROVIDER.lower().strip()
        is_general_mode = intent in ["GENERAL_KNOWLEDGE", "HOTEL_ANALOGY"]

        # Check explicit missing keys
        if provider == "openai":
            if not settings.OPENAI_API_KEY:
                err = (
                    "AI Provider is configured as 'openai', but OPENAI_API_KEY is not set in backend environment variables. "
                    "Please configure OPENAI_API_KEY in backend/.env or set AI_PROVIDER=auto to use the local operations engine."
                )
                return cls._create_error_response(conversation_id, err, db)
            response_text, tools_executed, action_proposal = await cls._execute_openai(
                db=db, ctx=ctx, query=cleaned_text, history=history_msgs[-6:], is_general_mode=is_general_mode
            )

        elif provider == "gemini":
            if not settings.GEMINI_API_KEY:
                err = (
                    "AI Provider is configured as 'gemini', but GEMINI_API_KEY is not set in backend environment variables. "
                    "Please configure GEMINI_API_KEY in backend/.env or set AI_PROVIDER=auto to use the local operations engine."
                )
                return cls._create_error_response(conversation_id, err, db)
            response_text, tools_executed, action_proposal = await cls._execute_gemini(
                db=db, ctx=ctx, query=cleaned_text, history=history_msgs[-6:], is_general_mode=is_general_mode
            )

        elif provider == "deterministic":
            response_text, tools_executed, action_proposal = await cls._execute_deterministic(
                db=db, ctx=ctx, query=cleaned_text, is_hindi=is_hindi, intent=intent
            )

        else: # "auto"
            executed = False
            # Try Gemini first if key exists
            if settings.GEMINI_API_KEY:
                try:
                    response_text, tools_executed, action_proposal = await cls._execute_gemini(
                        db=db, ctx=ctx, query=cleaned_text, history=history_msgs[-6:], is_general_mode=is_general_mode
                    )
                    executed = True
                except Exception as e:
                    logger.warning(f"Gemini execution failed in auto mode: {e}")

            # Try OpenAI if not executed and key exists
            if not executed and settings.OPENAI_API_KEY:
                try:
                    response_text, tools_executed, action_proposal = await cls._execute_openai(
                        db=db, ctx=ctx, query=cleaned_text, history=history_msgs[-6:], is_general_mode=is_general_mode
                    )
                    executed = True
                except Exception as e:
                    logger.warning(f"OpenAI execution failed in auto mode: {e}")

            # Fall back to high-precision Deterministic Router
            if not executed:
                response_text, tools_executed, action_proposal = await cls._execute_deterministic(
                    db=db, ctx=ctx, query=cleaned_text, is_hindi=is_hindi, intent=intent
                )

        # 7. Save Assistant Message
        tool_calls_payload = list(tools_executed)
        if action_proposal:
            tool_calls_payload.append({
                "type": "action_proposal",
                "action_id": action_proposal.action_id,
                "action_name": action_proposal.action_name,
                "parameters": action_proposal.parameters
            })

        asst_msg = AssistantMessage(
            conversation_id=conversation_id,
            sender="ASSISTANT",
            content=response_text,
            tool_calls=tool_calls_payload
        )
        db.add(asst_msg)

        # 8. Audit Log Tool Execution
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        tool_log = AssistantToolLog(
            hotel_id=hotel_id,
            user_id=user_id,
            tool_name=",".join(tools_executed) if tools_executed else ("general_knowledge" if is_general_mode else "direct_query"),
            parameters_json={"query": cleaned_text, "intent": intent, "tools": tools_executed},
            result_summary=response_text[:250],
            execution_duration_ms=duration_ms
        )
        db.add(tool_log)
        await db.commit()

        return {
            "conversation_id": conversation_id,
            "message": response_text,
            "tools_executed": tools_executed,
            "action_proposal": action_proposal,
            "action_executed": None,
            "timestamp": datetime.now(timezone.utc)
        }

    @staticmethod
    def _create_error_response(conv_id: str, err_msg: str, db: AsyncSession) -> Dict[str, Any]:
        return {
            "conversation_id": conv_id,
            "message": f"Configuration Notice: {err_msg}",
            "tools_executed": [],
            "action_proposal": None,
            "action_executed": None,
            "timestamp": datetime.now(timezone.utc)
        }

    # =================================================================
    # GOOGLE GEMINI EXECUTION ENGINE (BIMODAL)
    # =================================================================

    @classmethod
    async def _execute_gemini(
        cls,
        db: AsyncSession,
        ctx: TenantContext,
        query: str,
        history: List[AssistantMessage],
        is_general_mode: bool
    ) -> Tuple[str, List[str], Optional[ActionProposal]]:
        """
        Executes Google Gemini using REST API.
        In General Knowledge Mode: answers directly with code/examples, without forcing operational tools.
        In Hotel Operations Mode: passes typed tools, handles function calls, enforces RBAC and USALI.
        """
        key = settings.GEMINI_API_KEY
        # Multi-model redundancy list
        candidate_models = [
            settings.GEMINI_MODEL,
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3-flash-preview",
            "gemma-4-26b-a4b-it"
        ]
        # Deduplicate while preserving order
        models_to_try = list(dict.fromkeys(candidate_models))

        # -------------------------------------------------------------
        # A. GENERAL KNOWLEDGE MODE
        # -------------------------------------------------------------
        if is_general_mode:
            sys_inst = {
                "parts": [{
                    "text": (
                        f"You are the HotelOS AI Assistant for '{ctx.hotel.name}'.\n"
                        f"The user has asked a GENERAL KNOWLEDGE or CONCEPTUAL question.\n"
                        f"RULES:\n"
                        f"1. Answer directly and comprehensively using clear, friendly explanations.\n"
                        f"2. For programming, technology, or mathematics, always include practical code snippets (Python, JavaScript, etc.) and simple explanations.\n"
                        f"3. If the user asks for a hotel-themed analogy or example (e.g. 'Explain loops using a hotel example'), provide an imaginative hotel scenario (like inspecting 100 rooms or washing towels in laundry) without referencing private property records.\n"
                        f"4. Do NOT call operational tools for general knowledge questions.\n"
                        f"5. Respond in the user's language (English or Hindi/Hinglish)."
                    )
                }]
            }
            contents = []
            for m in history:
                role = "user" if m.sender == "USER" else "model"
                contents.append({"role": role, "parts": [{"text": m.content}]})
            contents.append({"role": "user", "parts": [{"text": query}]})

            for m_name in models_to_try:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={key}"
                    async with httpx.AsyncClient(timeout=25.0) as client:
                        resp = await client.post(url, json={
                            "system_instruction": sys_inst,
                            "contents": contents,
                            "generationConfig": {"maxOutputTokens": settings.AI_MAX_TOKENS}
                        })
                        if resp.status_code == 200:
                            data = resp.json()
                            text_parts = data["candidates"][0]["content"]["parts"]
                            ans = "\n".join(p["text"] for p in text_parts if "text" in p)
                            return ans, [], None
                        logger.warning(f"Model {m_name} returned HTTP {resp.status_code}")
                except Exception as ex:
                    logger.warning(f"Model {m_name} request error: {ex}")

            # Fallback to deterministic general knowledge handler
            return await cls._execute_deterministic_general(query=query, is_hindi=cls._detect_hindi(query))

        # -------------------------------------------------------------
        # B. HOTEL OPERATIONS MODE (WITH TYPED TOOLS)
        # -------------------------------------------------------------
        type_map = {
            "string": "STRING", "integer": "INTEGER", "number": "NUMBER",
            "boolean": "BOOLEAN", "object": "OBJECT", "array": "ARRAY"
        }

        def convert_param(p: Dict[str, Any]) -> Dict[str, Any]:
            out: Dict[str, Any] = {}
            t = p.get("type", "string").lower()
            out["type"] = type_map.get(t, "STRING")
            if "description" in p: out["description"] = p["description"]
            if "properties" in p: out["properties"] = {k: convert_param(v) for k, v in p["properties"].items()}
            if "required" in p: out["required"] = p["required"]
            return out

        gemini_functions = []
        for tool in LLM_TOOLS_SPEC:
            fn = tool["function"]
            decl: Dict[str, Any] = {"name": fn["name"], "description": fn["description"]}
            if "parameters" in fn and fn["parameters"].get("properties"):
                decl["parameters"] = convert_param(fn["parameters"])
            gemini_functions.append(decl)

        tools = [{"function_declarations": gemini_functions}]

        sys_inst = {
            "parts": [{
                "text": (
                    f"You are the HotelOS AI Operations Assistant for property '{ctx.hotel.name}'.\n"
                    f"Hotel ID: {ctx.hotel_id}. User Role: {ctx.role}.\n"
                    f"STRICT RULES:\n"
                    f"1. You MUST call available backend operational tools to retrieve live facts. Never guess or hallucinate hotel data.\n"
                    f"2. USALI Rule: Room revenue is earned on an accrual basis. Do NOT label operating contribution as Net Profit.\n"
                    f"3. Redact sensitive guest phone and card numbers.\n"
                    f"4. If proposing a consequential action (cleaning task, maintenance ticket), explain what you are proposing and ask for confirmation.\n"
                    f"5. Answer in professional English or Hindi depending on the language of the user."
                )
            }]
        }

        contents = []
        for m in history:
            role = "user" if m.sender == "USER" else "model"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        contents.append({"role": "user", "parts": [{"text": query}]})

        tools_executed: List[str] = []
        action_proposal: Optional[ActionProposal] = None

        for m_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={key}"
                async with httpx.AsyncClient(timeout=25.0) as client:
                    payload = {
                        "system_instruction": sys_inst,
                        "contents": contents,
                        "tools": tools,
                        "generationConfig": {"maxOutputTokens": settings.AI_MAX_TOKENS}
                    }
                    res1 = await client.post(url, json=payload)
                    if res1.status_code != 200:
                        logger.warning(f"Model {m_name} returned status {res1.status_code}: {res1.text[:200]}")
                        continue

                    data1 = res1.json()
                    candidates = data1.get("candidates", [])
                    if not candidates:
                        continue

                    model_content = candidates[0].get("content", {})
                    parts = model_content.get("parts", [])
                    function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

                    if not function_calls:
                        text_parts = [p["text"] for p in parts if "text" in p]
                        return "\n".join(text_parts), tools_executed, None

                    contents.append(model_content)

                    for fc in function_calls:
                        fn_name = fc["name"]
                        fn_args = fc.get("args", {})
                        tools_executed.append(fn_name)

                        # Consequential action interception
                        if fn_name in CONSEQUENTIAL_ACTIONS:
                            action_id = f"act_{uuid.uuid4().hex[:10]}"
                            action_proposal = ActionProposal(
                                action_id=action_id,
                                action_name=fn_name,
                                title=fn_name.replace("_", " ").title(),
                                parameters=fn_args,
                                impact_summary=f"Proposes {fn_name.replace('_', ' ')} with parameters: {fn_args}",
                                status="pending_confirmation"
                            )
                            tool_result = {
                                "status": "pending_user_confirmation",
                                "action_id": action_id,
                                "notice": "Action proposal created. Awaiting user confirmation before modifying hotel database."
                            }
                        elif fn_name in AVAILABLE_AI_TOOLS:
                            tool_fn = AVAILABLE_AI_TOOLS[fn_name]
                            tool_result = await tool_fn(db=db, ctx=ctx, **fn_args)
                        else:
                            tool_result = {"error": f"Tool '{fn_name}' not available"}

                        contents.append({
                            "role": "user",
                            "parts": [{
                                "functionResponse": {
                                    "name": fn_name,
                                    "response": tool_result
                                }
                            }]
                        })

                    res2 = await client.post(url, json={
                        "system_instruction": sys_inst,
                        "contents": contents,
                        "tools": tools,
                        "generationConfig": {"maxOutputTokens": settings.AI_MAX_TOKENS}
                    })
                    if res2.status_code == 200:
                        data2 = res2.json()
                        cand2 = data2.get("candidates", [])
                        if cand2:
                            synth_parts = cand2[0].get("content", {}).get("parts", [])
                            synth_text = "\n".join(p["text"] for p in synth_parts if "text" in p)
                            return synth_text, tools_executed, action_proposal

            except Exception as e:
                logger.warning(f"Gemini execution error with model {m_name}: {e}")

        # Fallback to deterministic hotel engine
        return await cls._execute_deterministic(db=db, ctx=ctx, query=query, is_hindi=cls._detect_hindi(query), intent="HOTEL_DATA")

    # =================================================================
    # OPENAI EXECUTION ENGINE (BIMODAL)
    # =================================================================

    @classmethod
    async def _execute_openai(
        cls,
        db: AsyncSession,
        ctx: TenantContext,
        query: str,
        history: List[AssistantMessage],
        is_general_mode: bool
    ) -> Tuple[str, List[str], Optional[ActionProposal]]:
        system_prompt = (
            f"You are the HotelOS AI Assistant for property '{ctx.hotel.name}'.\n"
            f"Hotel ID: {ctx.hotel_id}. User Role: {ctx.role}.\n"
            f"RULES:\n"
            f"1. For general knowledge/coding questions: answer directly with clear explanations and code snippets. Do not call operational tools.\n"
            f"2. For hotel operations questions: call backend tools to retrieve live verified facts. Never invent numbers.\n"
            f"3. Obey USALI definitions: room revenue is earned on an accrual basis. Do NOT label operating contribution as Net Profit.\n"
            f"4. Redact sensitive guest phone and card numbers.\n"
            f"5. Answer in professional English or Hindi depending on the language of the user."
        )

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for m in history:
            role = "user" if m.sender == "USER" else "assistant"
            messages.append({"role": role, "content": m.content})
        messages.append({"role": "user", "content": query})

        tools_executed: List[str] = []
        action_proposal: Optional[ActionProposal] = None

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            payload: Dict[str, Any] = {
                "model": settings.OPENAI_MODEL,
                "messages": messages,
                "max_tokens": settings.AI_MAX_TOKENS
            }
            if not is_general_mode:
                payload["tools"] = LLM_TOOLS_SPEC
                payload["tool_choice"] = "auto"

            resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code == 401:
                raise ValueError("OpenAI API authentication failed. The OPENAI_API_KEY is invalid.")
            if resp.status_code == 429:
                raise ValueError("OpenAI rate limit or quota exceeded.")
            if resp.status_code != 200:
                raise ValueError(f"OpenAI error (HTTP {resp.status_code}): {resp.text}")

            data = resp.json()
            choice = data["choices"][0]["message"]

            if choice.get("tool_calls"):
                messages.append(choice)
                for tc in choice["tool_calls"]:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"].get("arguments", "{}"))
                    tools_executed.append(fn_name)

                    if fn_name in CONSEQUENTIAL_ACTIONS:
                        action_id = f"act_{uuid.uuid4().hex[:10]}"
                        action_proposal = ActionProposal(
                            action_id=action_id,
                            action_name=fn_name,
                            title=fn_name.replace("_", " ").title(),
                            parameters=fn_args,
                            impact_summary=f"Proposes {fn_name.replace('_', ' ')} with parameters: {fn_args}",
                            status="pending_confirmation"
                        )
                        tool_res = {
                            "status": "pending_user_confirmation",
                            "action_id": action_id,
                            "notice": "Action proposed. Awaiting user confirmation before modifying database records."
                        }
                    elif fn_name in AVAILABLE_AI_TOOLS:
                        tool_fn = AVAILABLE_AI_TOOLS[fn_name]
                        tool_res = await tool_fn(db=db, ctx=ctx, **fn_args)
                    else:
                        tool_res = {"error": f"Tool {fn_name} not found"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": fn_name,
                        "content": json.dumps(tool_res)
                    })

                synth_resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": settings.OPENAI_MODEL,
                        "messages": messages,
                        "max_tokens": settings.AI_MAX_TOKENS
                    }
                )
                synth_data = synth_resp.json()
                return synth_data["choices"][0]["message"]["content"], tools_executed, action_proposal

            return choice.get("content", ""), tools_executed, action_proposal

    # =================================================================
    # DETERMINISTIC GENERAL KNOWLEDGE ENGINE (OFFLINE RESILIENCE)
    # =================================================================

    @classmethod
    async def _execute_deterministic_general(
        cls,
        query: str,
        is_hindi: bool
    ) -> Tuple[str, List[str], Optional[ActionProposal]]:
        """
        High-precision conceptual answers for general knowledge and programming topics
        when the external LLM is offline, unconfigured, or temporarily rate-limited.
        """
        q = query.lower()

        # Hotel Analogy for Loops
        if any(w in q for w in ["hotel example", "hotel analogy", "using a hotel", "होटल का उदाहरण"]) and "loop" in q:
            if is_hindi:
                ans = (
                    "**होटल के उदाहरण से लूप (Loop) को समझें:**\n\n"
                    "प्रोग्रामिंग में **लूप** एक ही काम को बार-बार दोहराने का स्वचालित तरीका है।\n\n"
                    "### 1. `for` लूप (कमरों की निश्चित संख्या):\n"
                    "मान लीजिए हाउसकीपर को कमरा 101 से 108 तक कुल 8 कमरों का निरीक्षण करना है:\n"
                    "```python\n"
                    "for room_number in range(101, 109):\n"
                    "    inspect_room(room_number)\n"
                    "```\n"
                    "*यह क्रिया ठीक 8 बार दोहराई जाएगी और फिर रुक जाएगी।*\n\n"
                    "### 2. `while` लूप (शर्त पर आधारित):\n"
                    "लॉन्ड्री टीम तब तक तौलिए धोती रहती है जब तक लॉन्ड्री बिन खाली न हो जाए:\n"
                    "```python\n"
                    "while laundry_bin.has_dirty_towels():\n"
                    "    wash_towel_batch()\n"
                    "```\n"
                    "*जब तक गंदे तौलिए हैं, वाशिंग मशीन चलती रहेगी।*\n\n"
                    "लूप्स की मदद से सॉफ्टवेयर को हर कमरे के लिए अलग कोड नहीं लिखना पड़ता!"
                )
            else:
                ans = (
                    "Here is how **programming loops** work using a hotel operations analogy:\n\n"
                    "In programming, a **loop** repeats a block of code multiple times without rewriting it.\n\n"
                    "### 1. The `for` Loop (Known Count of Rooms)\n"
                    "Imagine a housekeeper tasked with inspecting Room 101 through 108 (8 rooms total):\n"
                    "```python\n"
                    "# Since we know there are exactly 8 rooms:\n"
                    "for room_number in range(101, 109):\n"
                    "    inspect_room(room_number)\n"
                    "```\n"
                    "*The inspection runs exactly 8 times, once for each room, and stops.*\n\n"
                    "### 2. The `while` Loop (Condition-Controlled)\n"
                    "Imagine the laundry team washing towels from the checkout bin until it is empty:\n"
                    "```python\n"
                    "# Repeat as long as the bin contains dirty towels:\n"
                    "while laundry_bin.has_dirty_towels():\n"
                    "    wash_towel_batch()\n"
                    "```\n"
                    "*The cycle keeps running until `has_dirty_towels()` becomes False.*\n\n"
                    "### 3. Nested Loops (Floors and Rooms)\n"
                    "```python\n"
                    "for floor in [1, 2, 3]:\n"
                    "    for room in get_rooms_on_floor(floor):\n"
                    "        deliver_morning_newspaper(room)\n"
                    "```\n\n"
                    "Loops automate repetitive operational tasks cleanly without duplicate code!"
                )
            return ans, [], None

        # General Loops
        if "loop" in q or "लूप" in q:
            if is_hindi:
                ans = (
                    "**लूप (Loop) क्या है?**\n\n"
                    "प्रोग्रामिंग में **लूप** एक नियंत्रण संरचना (Control Structure) है जो किसी कोड ब्लॉक को बार-बार दोहराने का काम करती है जब तक कि कोई निश्चित शर्त पूरी न हो जाए।\n\n"
                    "### 1. `for` लूप (For Loop):\n"
                    "जब आपको पता हो कि कोड को कितनी बार चलाना है:\n"
                    "```python\n"
                    "for i in range(5):\n"
                    "    print(i)\n"
                    "```\n"
                    "*यह 0 से 4 तक की संख्याएं प्रिंट करता है।*\n\n"
                    "### 2. `while` लूप (While Loop):\n"
                    "जब तक कोई शर्त `True` रहती है:\n"
                    "```python\n"
                    "count = 0\n"
                    "while count < 3:\n"
                    "    print(count)\n"
                    "    count += 1\n"
                    "```\n\n"
                    "**मुख्य लाभ:** कोड का पुन: उपयोग, समय की बचत, और सूचियों (Lists/Arrays) पर काम करने में आसानी।"
                )
            else:
                ans = (
                    "A **loop** is a fundamental programming structure that repeats a block of code multiple times until a specified condition is met or for a set number of iterations.\n\n"
                    "### 1. The `for` Loop (Count-Controlled)\n"
                    "Used when you know how many times code should repeat:\n"
                    "```python\n"
                    "for i in range(5):\n"
                    "    print(i)\n"
                    "```\n"
                    "*This prints numbers from 0 to 4.*\n\n"
                    "### 2. The `while` Loop (Condition-Controlled)\n"
                    "Repeats as long as a boolean condition evaluates to `True`:\n"
                    "```python\n"
                    "count = 0\n"
                    "while count < 3:\n"
                    "    print(f'Count is: {count}')\n"
                    "    count += 1\n"
                    "```\n\n"
                    "### Key Benefits:\n"
                    "- **Automation**: Eliminates repetitive copy-paste code.\n"
                    "- **Iteration**: Easily processes elements in arrays, lists, or database records."
                )
            return ans, [], None

        # General Functions
        if "function" in q or "फ़ंक्शन" in q or "फंक्शन" in q:
            if is_hindi:
                ans = (
                    "**पायथन फ़ंक्शन (Python Functions):**\n\n"
                    "फ़ंक्शन एक पुन: प्रयोज्य (Reusable) कोड ब्लॉक होता है जो किसी विशिष्ट कार्य को पूरा करने के लिए बनाया जाता है। पायथन में इसे `def` कीवर्ड से परिभाषित किया जाता है।\n\n"
                    "### उदाहरण:\n"
                    "```python\n"
                    "def greet(name: str) -> str:\n"
                    "    \"\"\"अतिथि का स्वागत करता है।\"\"\"\n"
                    "    return f\"नमस्ते, {name}!\"\n\n"
                    "# फ़ंक्शन कॉल करना:\n"
                    "message = greet(\"राजेश\")\n"
                    "print(message)  # आउटपुट: नमस्ते, राजेश!\n"
                    "```\n\n"
                    "### मुख्य घटक:\n"
                    "- **`def` कीवर्ड**: फ़ंक्शन शुरू करने के लिए।\n"
                    "- **पैरामीटर्स (Parameters)**: फ़ंक्शन में इनपुट देने के लिए।\n"
                    "- **`return` स्टेटमेंट**: परिणाम वापस भेजने के लिए।"
                )
            else:
                ans = (
                    "In Python, a **function** is a named, reusable block of code designed to perform a specific action. You define it once using the `def` keyword and invoke it whenever needed.\n\n"
                    "### Example:\n"
                    "```python\n"
                    "def calculate_total(base_rate: float, tax_pct: float = 0.12) -> float:\n"
                    "    \"\"\"Calculates total bill including tax.\"\"\"\n"
                    "    tax_amount = base_rate * tax_pct\n"
                    "    return base_rate + tax_amount\n\n"
                    "# Calling the function:\n"
                    "total = calculate_total(2500.0)\n"
                    "print(f\"Total Bill: ₹{total:.2f}\")  # Output: Total Bill: ₹2800.00\n"
                    "```\n\n"
                    "### Key Components:\n"
                    "- **`def` statement**: Declares the function signature.\n"
                    "- **Arguments/Parameters**: Inputs passed into the function.\n"
                    "- **`return` statement**: Hands the computed output back to the caller.\n"
                    "- **Modularity**: Keeps programs clean, testable, and maintainable."
                )
            return ans, [], None

        # General Python / Programming concepts
        ans = (
            f"I understand your question regarding '{query}'.\n\n"
            f"As your HotelOS Assistant, I support both general technical knowledge (programming, algorithms, math) "
            f"and your hotel's live operational tools.\n\n"
            f"Could you please share more details or ask a specific programming question, such as:\n"
            f"- *'What is a loop?'*\n"
            f"- *'Explain Python functions with code'* \n"
            f"- *'How does recursion work?'*"
        ) if not is_hindi else (
            f"मैं आपके प्रश्न '{query}' को समझता हूँ।\n\n"
            f"मैं सामान्य प्रोग्रामिंग ज्ञान और आपके होटल के लाइव डेटा दोनों में मदद कर सकता हूँ।\n"
            f"कृपया विशिष्ट प्रश्न पूछें, जैसे:\n"
            f"- *'लूप क्या है?'*\n"
            f"- *'पायथन फ़ंक्शन समझाओ'*"
        )
        return ans, [], None

    # =================================================================
    # DETERMINISTIC HOTEL OPERATIONS ENGINE (GROUNDED IN REAL DB)
    # =================================================================

    @classmethod
    async def _execute_deterministic(
        cls,
        db: AsyncSession,
        ctx: TenantContext,
        query: str,
        is_hindi: bool,
        intent: str
    ) -> Tuple[str, List[str], Optional[ActionProposal]]:
        """
        High-precision intent router that checks RBAC permissions,
        invokes typed backend tools against the real database, creates action proposals for mutations,
        and formats grounded responses adhering to USALI guidelines.
        """
        q = query.lower()
        tools_called: List[str] = []

        # If intent is general knowledge, route directly to general knowledge handler
        if intent in ["GENERAL_KNOWLEDGE", "HOTEL_ANALOGY"]:
            return await cls._execute_deterministic_general(query=query, is_hindi=is_hindi)

        # Extract Room Number
        room_match = re.search(r'(?:room|कमरा|no\.?|नंबर)?\s*(\d{3,4})', q)
        extracted_room = room_match.group(1) if room_match else None

        # Extract Floor Number
        floor_match = re.search(r'(?:floor|मंज़िल)\s*(\d+)|(\d+)(?:st|nd|rd|th)\s*floor', q)
        extracted_floor = int(floor_match.group(1) or floor_match.group(2)) if floor_match else None

        # -------------------------------------------------------------
        # 1. ACTION PROPOSALS (CONSTRAINED)
        # -------------------------------------------------------------

        # Maintenance Ticket
        if any(w in q for w in ["repair", "fix", "broken", "leak", "खराब", "मरम्मत", "समस्या"]) and any(w in q for w in ["create", "log", "ticket", "लॉग", "बनाओ", "दर्ज", "report"]):
            tools_called.append("create_maintenance_ticket")
            if ctx.role not in ["OWNER", "MANAGER", "RECEPTIONIST", "MAINTENANCE"]:
                msg = f"Permission denied: Your role '{ctx.role}' is not authorized to log maintenance tickets."
                return msg, tools_called, None

            if not extracted_room:
                msg = "कृपया बताइए कि किस कमरे के लिए मेंटेनेंस टिकट बनाना है? (उदा. 'कमरा 101 का AC खराब है')" if is_hindi else "Please specify which room number requires maintenance (e.g. 'Create maintenance ticket for Room 301 AC leak')."
                return msg, tools_called, None

            title = "Air Conditioner Malfunction" if "ac" in q else ("Plumbing Leak" if ("leak" in q or "water" in q) else ("Electrical Issue" if "light" in q else "Maintenance Defect"))
            prio = "CRITICAL" if any(w in q for w in ["critical", "emergency", "urgent", "गंभीर"]) else "HIGH" if any(w in q for w in ["high", "जल्दी"]) else "MEDIUM"

            action_id = f"act_{uuid.uuid4().hex[:10]}"
            params = {
                "room_number": extracted_room,
                "title": title,
                "description": query,
                "priority": prio
            }
            impact = f"Will log maintenance ticket for Room {extracted_room} with priority {prio}." + (" Room will be blocked from sales." if prio == "CRITICAL" else "")
            proposal = ActionProposal(
                action_id=action_id,
                action_name="create_maintenance_ticket",
                title="Create Maintenance Ticket",
                parameters=params,
                impact_summary=impact,
                status="pending_confirmation"
            )

            if is_hindi:
                ans = f"मैंने कमरा **{extracted_room}** के लिए मेंटेनेंस टिकट का प्रस्ताव तैयार किया है:\n- **शीर्षक:** {title}\n- **प्राथमिकता:** `{prio}`\n- **विवरण:** {query}\n\nक्या आप इसे दर्ज करना चाहते हैं? कृपया नीचे **कन्फर्म करें**।"
            else:
                ans = f"I have prepared an action proposal to create a maintenance ticket for **Room {extracted_room}**:\n- **Issue:** {title}\n- **Priority:** `{prio}`\n- **Impact:** {impact}\n\nPlease review the details below and confirm to execute this ticket."

            return ans, tools_called, proposal

        # Housekeeping Task
        if any(w in q for w in ["clean", "housekeep", "sweep", "mop", "सफाई", "क्लीनिंग"]) and any(w in q for w in ["create", "task", "बनाओ", "शुरू", "भेजो"]):
            tools_called.append("create_housekeeping_task")
            if ctx.role not in ["OWNER", "MANAGER", "RECEPTIONIST", "HOUSEKEEPER"]:
                msg = f"Permission denied: Your role '{ctx.role}' is not authorized to create housekeeping tasks."
                return msg, tools_called, None

            if not extracted_room:
                msg = "किस कमरे की सफाई के लिए टास्क बनाना है? (उदा. 'कमरा 204 की सफाई का टास्क बनाओ')" if is_hindi else "Which room should I create a cleaning task for? (e.g. 'Create housekeeping task for Room 204')."
                return msg, tools_called, None

            prio = "HIGH" if any(w in q for w in ["urgent", "high", "जल्दी"]) else "MEDIUM"
            action_id = f"act_{uuid.uuid4().hex[:10]}"
            params = {
                "room_number": extracted_room,
                "priority": prio,
                "notes": query
            }
            impact = f"Creates a standard 5-point turnover cleaning task for Room {extracted_room} and marks room as dirty."
            proposal = ActionProposal(
                action_id=action_id,
                action_name="create_housekeeping_task",
                title="Create Housekeeping Task",
                parameters=params,
                impact_summary=impact,
                status="pending_confirmation"
            )

            if is_hindi:
                ans = f"मैंने कमरा **{extracted_room}** की सफाई का टास्क तैयार किया है (प्राथमिकता: `{prio}`)। क्या आप इसे सक्रिय करना चाहते हैं? कृपया नीचे **कन्फर्म करें**।"
            else:
                ans = f"I have prepared an action proposal to create a housekeeping cleaning task for **Room {extracted_room}** (Priority: `{prio}`).\n\nPlease confirm below to schedule this cleaning task."

            return ans, tools_called, proposal

        # Assign Task
        if "assign" in q and any(w in q for w in ["housekeep", "task", "clean", "सफाई", "टास्क"]):
            tools_called.append("assign_housekeeping_task")
            if ctx.role not in ["OWNER", "MANAGER"]:
                msg = f"Permission denied: Only OWNER or MANAGER can reassign housekeeping tasks."
                return msg, tools_called, None

            msg = "Please confirm the task ID and staff member name to assign." if not is_hindi else "कृपया टास्क आईडी और स्टाफ सदस्य का नाम बताएं।"
            return msg, tools_called, None

        # -------------------------------------------------------------
        # 2. OPERATIONAL READ QUERIES (GROUNDED IN REAL DATABASE)
        # -------------------------------------------------------------

        # Specific Room Status
        if extracted_room and any(w in q for w in ["status", "clean", "ready", "condition", "स्थिति", "तैयार", "साफ", "check"]):
            tools_called.append("get_room_cleaning_status")
            res = await AVAILABLE_AI_TOOLS["get_room_cleaning_status"](db=db, ctx=ctx, room_number=extracted_room)
            if not res.get("found"):
                return f"Room {extracted_room} was not found in this hotel property.", tools_called, None

            st = res["room_status"]
            task_st = res.get("latest_task_status", "No Active Task")
            if is_hindi:
                ans = f"**कमरा {extracted_room} की वर्तमान स्थिति:**\n- **स्थिति:** `{st}`\n- **सफाई टास्क स्थिति:** `{task_st}`\n- **मंज़िल:** {res.get('floor')}\n- **प्रकार:** {res.get('room_type')}"
            else:
                ans = f"**Room {extracted_room} Operational Status:**\n- **Room State:** `{st}`\n- **Housekeeping Task:** `{task_st}`\n- **Floor:** {res.get('floor')}\n- **Category:** {res.get('room_type')}"
            return ans, tools_called, None

        # Rooms by Floor
        if extracted_floor is not None and "floor" in q:
            tools_called.append("get_rooms_by_floor")
            res = await AVAILABLE_AI_TOOLS["get_rooms_by_floor"](db=db, ctx=ctx, floor_number=extracted_floor)
            cnt = res.get("room_count", 0)
            if is_hindi:
                ans = f"मंज़िल **{extracted_floor}** पर कुल **{cnt} कमरे** हैं:\n"
            else:
                ans = f"Floor **{extracted_floor}** has **{cnt} rooms**:\n"
            lines = [f"- **Room {r['room_number']}**: `{r['status']}` ({r['room_type']})" for r in res.get("rooms", [])]
            ans += "\n".join(lines)
            return ans, tools_called, None

        # Rooms Under Maintenance / Blocked
        if any(w in q for w in ["maintenance", "blocked", "repair", "खराब", "मरम्मत"]) and any(w in q for w in ["room", "which", "list", "कमरे", "कौन"]):
            tools_called.append("get_rooms_under_maintenance")
            res = await AVAILABLE_AI_TOOLS["get_rooms_under_maintenance"](db=db, ctx=ctx)
            cnt = res.get("blocked_count", 0)
            if cnt == 0:
                ans = "कोई भी कमरा मेंटेनेंस के लिए ब्लॉक नहीं है।" if is_hindi else "No rooms are currently blocked under maintenance."
            else:
                ans = f"**{cnt} कमरे मेंटेनेंस के कारण ब्लॉक हैं:**\n" if is_hindi else f"**{cnt} rooms are currently blocked for maintenance:**\n"
                lines = [f"- **Room {r['room_number']}**: {r['open_tickets_count']} open tickets (Floor: {r['floor']})" for r in res.get("rooms", [])]
                ans += "\n".join(lines)
            return ans, tools_called, None

        # Vacant Rooms
        if any(w in q for w in ["vacant", "available", "empty", "free", "खाली", "उपलब्ध"]):
            tools_called.append("get_vacant_rooms")
            clean_only = "clean" in q or "साफ" in q
            res = await AVAILABLE_AI_TOOLS["get_vacant_rooms"](db=db, ctx=ctx, clean_only=clean_only)
            v_count = res["vacant_count"]
            clean_count = res["clean_ready_to_sell"]
            dirty_count = res["dirty_needs_cleaning"]

            if is_hindi:
                ans = (
                    f"आज होटल में **कुल {v_count} कमरे खाली** हैं:\n"
                    f"- **{clean_count} कमरे साफ (Ready to sell)**\n"
                    f"- **{dirty_count} कमरे गंदे (Awaiting housekeeping)**"
                )
            else:
                ans = (
                    f"There are currently **{v_count} vacant rooms**:\n"
                    f"- **{clean_count} Vacant Clean** (Ready for check-in)\n"
                    f"- **{dirty_count} Vacant Dirty** (Awaiting housekeeping)"
                )
            if res.get("rooms"):
                sample = ", ".join(f"`{r['room_number']}`" for r in res["rooms"][:8])
                ans += f"\n\n**Available Rooms:** {sample}"
            return ans, tools_called, None

        # Occupied Rooms
        if any(w in q for w in ["occup", "stay", "booked", "भरे", "ऑक्यूपेंसी"]):
            tools_called.append("get_occupied_rooms")
            res = await AVAILABLE_AI_TOOLS["get_occupied_rooms"](db=db, ctx=ctx)
            occ_count = res["occupied_count"]
            if is_hindi:
                ans = f"वर्तमान में **{occ_count} कमरे भरे हुए (Occupied)** हैं।"
            else:
                ans = f"Currently, there are **{occ_count} occupied rooms** with active guest stays."
            if res.get("rooms"):
                lines = [f"- **Room {r['room_number']}**: {r['guest_name']} (Phone: {r.get('guest_phone', 'Masked')}, Checkout: {r['expected_check_out'][:10] if r['expected_check_out'] else 'N/A'})" for r in res["rooms"][:6]]
                ans += "\n\n" + "\n".join(lines)
            return ans, tools_called, None

        # Check-ins & Check-outs
        if any(w in q for w in ["checkin", "check-in", "arrival", "आगमन", "चेक-इन"]):
            tools_called.append("get_today_checkins")
            res = await AVAILABLE_AI_TOOLS["get_today_checkins"](db=db, ctx=ctx)
            cnt = res.get("count", 0)
            if is_hindi:
                ans = f"आज कुल **{cnt} गेस्ट चेक-इन** निर्धारित हैं:\n"
            else:
                ans = f"There are **{cnt} guest check-ins scheduled for today**:\n"
            lines = [f"- **Room {c['room_number']}**: {c['guest_name']} ({c['time']}, Status: `{c['status']}`)" for c in res.get("checkins", [])]
            ans += "\n".join(lines) if lines else "- No scheduled check-ins remaining today."
            return ans, tools_called, None

        if any(w in q for w in ["checkout", "check-out", "departure", "निकास", "चेक-आउट"]):
            tools_called.append("get_today_checkouts")
            res = await AVAILABLE_AI_TOOLS["get_today_checkouts"](db=db, ctx=ctx)
            cnt = res.get("count", 0)
            if is_hindi:
                ans = f"आज कुल **{cnt} गेस्ट चेक-आउट** निर्धारित हैं:\n"
            else:
                ans = f"There are **{cnt} guest departures scheduled for today**:\n"
            lines = [f"- **Room {c['room_number']}**: {c['guest_name']} (Due: ₹{c['balance_due']:,.2f}, Time: {c['expected_time']})" for c in res.get("checkouts", [])]
            ans += "\n".join(lines) if lines else "- No scheduled departures remaining today."
            return ans, tools_called, None

        if any(w in q for w in ["booking", "reservation", "stay", "बुकिंग"]):
            if "upcoming" in q or "अगली" in q or "next" in q:
                tools_called.append("get_upcoming_reservations")
                res = await AVAILABLE_AI_TOOLS["get_upcoming_reservations"](db=db, ctx=ctx, days=7)
                cnt = res.get("upcoming_count", 0)
                ans = f"Found **{cnt} upcoming reservations** over the next 7 days." if not is_hindi else f"अगले 7 दिनों में कुल **{cnt} आगामी बुकिंग्स** हैं।"
                lines = [f"- **Room {r['room_number']}**: {r['guest_name']} (Check-in: {r['check_in_date']})" for r in res.get("reservations", [])[:5]]
                if lines: ans += "\n\n" + "\n".join(lines)
                return ans, tools_called, None
            else:
                tools_called.append("get_today_bookings")
                res = await AVAILABLE_AI_TOOLS["get_today_bookings"](db=db, ctx=ctx)
                ci = res["today_checkins_count"]
                co = res["today_checkouts_count"]
                active = res["total_active_stays"]
                ans = (
                    f"**Today's Bookings Overview:**\n"
                    f"- **Today's Check-ins:** {ci}\n"
                    f"- **Today's Check-outs:** {co}\n"
                    f"- **Total Active Stays:** {active}"
                ) if not is_hindi else (
                    f"**आज की बुकिंग स्थिति:**\n"
                    f"- **आज के चेक-इन:** {ci}\n"
                    f"- **आज के चेक-आउट:** {co}\n"
                    f"- **सक्रिय गेस्ट स्टे:** {active}"
                )
                return ans, tools_called, None

        # Housekeeping: Dirty rooms & tasks
        if any(w in q for w in ["housekeep", "cleaning", "dirty", "dusting", "सफाई", "झाड़ू", "हाउसकीपिंग"]):
            if "need" in q or "waiting" in q or "गंदे" in q or "बाकी" in q:
                tools_called.append("get_rooms_needing_cleaning")
                res = await AVAILABLE_AI_TOOLS["get_rooms_needing_cleaning"](db=db, ctx=ctx)
                cnt = res.get("dirty_rooms_count", len(res.get("rooms", [])))
                if is_hindi:
                    ans = f"कुल **{cnt} कमरों में सफाई की आवश्यकता है**:\n"
                else:
                    ans = f"There are **{cnt} rooms currently needing cleaning turnover**:\n"
                lines = [f"- **Room {r['room_number']}**: `{r['status']}` ({r.get('floor', 'Floor')})" for r in res.get("rooms", [])]
                ans += "\n".join(lines) if lines else "- All rooms are clean."
                return ans, tools_called, None

            if "staff" in q or "attendant" in q or "कर्मचारी" in q:
                tools_called.append("get_staff_pending_tasks")
                res = await AVAILABLE_AI_TOOLS["get_staff_pending_tasks"](db=db, ctx=ctx)
                ans = "**Housekeeping Staff Task Workload:**\n" if not is_hindi else "**हाउसकीपिंग स्टाफ टास्क विवरण:**\n"
                for s in res.get("staff_workload", []):
                    ans += f"- **{s['staff_name']}**: {s['pending_tasks_count']} pending tasks\n"
                ans += f"\n- **Unassigned Pending Tasks:** {res.get('unassigned_tasks_count', 0)}"
                return ans, tools_called, None

            tools_called.append("get_housekeeping_summary")
            res = await AVAILABLE_AI_TOOLS["get_housekeeping_summary"](db=db, ctx=ctx)
            ans = (
                f"**Housekeeping Status Overview:**\n"
                f"- **Clean & Ready to Sell:** {res['clean_ready']}\n"
                f"- **Dirty (Pending Cleaning):** {res['dirty_pending']}\n"
                f"- **Inspection Pending:** {res['inspection_pending']}\n"
                f"- **Active Tasks Assigned:** {res['active_cleaning_tasks']}"
            ) if not is_hindi else (
                f"**हाउसकीपिंग रिपोर्ट:**\n"
                f"- **साफ कमरे (Ready):** {res['clean_ready']}\n"
                f"- **सफाई बाकी (Dirty):** {res['dirty_pending']}\n"
                f"- **निरीक्षण बाकी:** {res['inspection_pending']}\n"
                f"- **सक्रिय सफाई टास्क:** {res['active_cleaning_tasks']}"
            )
            return ans, tools_called, None

        # Maintenance Requests
        if any(w in q for w in ["maintenance", "ticket", "repair", "breakdown", "geyser", "मरम्मत", "खराब"]):
            if "unresolved" in q or "issue" in q:
                tools_called.append("get_rooms_with_unresolved_maintenance")
                res = await AVAILABLE_AI_TOOLS["get_rooms_with_unresolved_maintenance"](db=db, ctx=ctx)
                cnt = res.get("rooms_affected_count", 0)
                ans = f"Found **{cnt} rooms with unresolved maintenance tickets**:\n" if not is_hindi else f"**{cnt} कमरों में अनसुलझी मेंटेनेंस समस्याएं हैं**:\n"
                for r in res.get("rooms", []):
                    ans += f"- **Room {r['room_number']}**: {len(r['open_tickets'])} open ticket(s)\n"
                return ans, tools_called, None

            tools_called.append("get_pending_maintenance_requests")
            res = await AVAILABLE_AI_TOOLS["get_pending_maintenance_requests"](db=db, ctx=ctx)
            cnt = res.get("open_tickets_count", 0)
            crit = res.get("critical_count", 0)
            if cnt == 0:
                ans = "कोई पेंडिंग मेंटेनेंस टिकट नहीं है। सभी उपकरण चालू हैं।" if is_hindi else "No open maintenance tickets found. All rooms and assets are operational."
            else:
                ans = f"There are currently **{cnt} open maintenance tickets** ({crit} critical):\n" if not is_hindi else f"वर्तमान में **{cnt} मेंटेनेंस टिकट खुले हैं** ({crit} क्रिटिकल):\n"
                lines = [f"- **Room {t['room_number']}**: {t['title']} (Priority: `{t['priority']}`, Status: `{t['status']}`)" for t in res.get("tickets", [])[:6]]
                ans += "\n".join(lines)
            return ans, tools_called, None

        # Inventory & Stock
        if any(w in q for w in ["inventory", "stock", "linen", "towel", "sheet", "toiletries", "सामग्री", "तौलिया", "चादर", "स्टॉक"]):
            if "quantity" in q or "quantities" in q or "कितनी" in q or "संख्या" in q:
                tools_called.append("get_inventory_quantities")
                res = await AVAILABLE_AI_TOOLS["get_inventory_quantities"](db=db, ctx=ctx)
                ans = "**Current Inventory Stock Quantities:**\n" if not is_hindi else "**वर्तमान इन्वेंट्री स्टॉक मात्रा:**\n"
                for it in res.get("items", [])[:8]:
                    ans += f"- **{it['name']}** ({it['category']}): {it['total_available']} in storage, {it['in_rooms']} in rooms\n"
                return ans, tools_called, None

            tools_called.append("get_low_stock_items")
            res = await AVAILABLE_AI_TOOLS["get_low_stock_items"](db=db, ctx=ctx)
            low_count = res.get("low_stock_count", 0)
            if low_count == 0:
                ans = "All inventory items and linens are stocked above minimum safety thresholds." if not is_hindi else "सभी इन्वेंट्री व चादरें पर्याप्त मात्रा में उपलब्ध हैं।"
            else:
                ans = f"**{low_count} inventory categories are running below safety thresholds:**\n" if not is_hindi else f"**{low_count} इन्वेंट्री श्रेणियों में स्टॉक कम है:**\n"
                for it in res.get("items", []):
                    ans += f"- **{it['name']}**: {it['current_stock']} on hand (Threshold: {it['threshold']}, Deficit: -{it['deficit']})\n"
            return ans, tools_called, None

        # Financial Performance
        if any(w in q for w in ["revenue", "expense", "collection", "profit", "contribution", "कमाई", "रेवेन्यू", "खर्चा", "कलेक्शन"]):
            tools_called.append("get_revenue_summary")
            period = "yesterday" if ("yesterday" in q or "कल" in q) else ("month" if ("month" in q or "महीना" in q) else "today")
            res = await AVAILABLE_AI_TOOLS["get_revenue_summary"](db=db, ctx=ctx, period=period)

            if not res.get("authorized"):
                return res.get("message", "Unauthorized to view financial records."), tools_called, None

            er = res["earned_revenue_accrual"]
            col = res["cash_collections_inflow"]
            exp = res["operating_expenses"]
            oc = res["operating_contribution"]

            if is_hindi:
                ans = (
                    f"**वित्तीय सारांश ({period.capitalize()}):**\n"
                    f"- **अर्जित रेवेन्यू (Accrual Earned):** ₹{er:,.2f}\n"
                    f"- **कैश/UPI कलेक्शन:** ₹{col:,.2f}\n"
                    f"- **ऑपरेटिंग खर्चे:** ₹{exp:,.2f}\n"
                    f"- **ऑपरेटिंग कॉन्ट्रिब्यूशन:** ₹{oc:,.2f}\n\n"
                    f"*(नोट: USALI मानकों के अनुसार इसे नेट प्रॉफिट नहीं बल्कि ऑपरेटिंग कॉन्ट्रिब्यूशन कहा जाता है।)*"
                )
            else:
                ans = (
                    f"**USALI Financial Summary ({period.capitalize()}):**\n"
                    f"- **Earned Revenue (Accrual):** ₹{er:,.2f}\n"
                    f"- **Cash Collections Received:** ₹{col:,.2f}\n"
                    f"- **Operating Expenses Recorded:** ₹{exp:,.2f}\n"
                    f"- **Operating Contribution:** ₹{oc:,.2f}\n\n"
                    f"*(Note: Under USALI lodging rules, this is Operating Contribution before corporate taxes, debt service, and capital allocations.)*"
                )
            return ans, tools_called, None

        # Outstanding Balances
        if any(w in q for w in ["balance", "due", "unpaid", "pending payment", "बाकी", "बकाया"]):
            tools_called.append("get_outstanding_balances")
            res = await AVAILABLE_AI_TOOLS["get_outstanding_balances"](db=db, ctx=ctx)
            if not res.get("authorized"):
                return "Unauthorized to view guest balances.", tools_called, None

            tot = res.get("total_outstanding_amount", 0)
            cnt = res.get("stays_with_due_count", 0)
            ans = f"There is **₹{tot:,.2f} in outstanding balance dues** across {cnt} active guest stays." if not is_hindi else f"वर्तमान में **{cnt} कमरों में कुल ₹{tot:,.2f} बकाया** है।"
            lines = [f"- Room {r['room_number']} ({r['guest_name']}): ₹{r['balance_due']:,.2f} due (Phone: {r.get('guest_phone', 'Masked')})" for r in res.get("records", [])[:5]]
            if lines: ans += "\n\n" + "\n".join(lines)
            return ans, tools_called, None

        # General Operational Snapshot
        tools_called.append("get_room_status")
        res = await AVAILABLE_AI_TOOLS["get_room_status"](db=db, ctx=ctx)
        s = res.get("summary", {})
        if is_hindi:
            ans = (
                f"नमस्ते! मैं आपका **HotelOS AI सहायक** हूँ।\n\n"
                f"आपके होटल में इस समय **{s.get('total', 0)} कुल कमरे** हैं ({s.get('occupied', 0)} भरे, {s.get('vacant_clean', 0)} साफ खाली, {s.get('vacant_dirty', 0)} गंदे)।\n\n"
                f"आप मुझसे पूछ सकते हैं:\n"
                f"- **होटल प्रश्न**: 'आज कितने कमरे खाली हैं?', 'आज का रेवेन्यू दिखाओ'\n"
                f"- **सामान्य ज्ञान**: 'लूप क्या है?', 'पायथन फ़ंक्शन समझाओ'"
            )
        else:
            ans = (
                f"Hello! I'm your **HotelOS AI Assistant**.\n\n"
                f"Your property has **{s.get('total', 0)} rooms** ({s.get('occupied', 0)} occupied, {s.get('vacant_clean', 0)} vacant clean, {s.get('vacant_dirty', 0)} vacant dirty).\n\n"
                f"You can ask me:\n"
                f"- **Hotel Operations**: *'How many rooms are vacant today?'*, *'What was yesterday's revenue?'*\n"
                f"- **General Knowledge**: *'What is a loop?'*, *'Explain Python functions'*, *'Explain loops using a hotel example'*"
            )
        return ans, tools_called, None

    @staticmethod
    def _detect_hindi(text: str) -> bool:
        """Detects Devanagari script or common Hinglish hospitality tokens."""
        if re.search(r'[\u0900-\u097F]', text):
            return True
        hinglish_tokens = [
            "kamra", "kitne", "khali", "aaj", "safai", "marammat", "batao",
            "kripya", "hote", "banao", "bhare", "karo", "kab", "samjhao"
        ]
        words = text.lower().split()
        return any(t in words for t in hinglish_tokens)


# Convenient module-level aliases
AIOperationsService = AIHotelAssistantService
classify_intent = AIHotelAssistantService.classify_intent

