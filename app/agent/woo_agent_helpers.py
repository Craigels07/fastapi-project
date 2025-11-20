from app.agent.models import WhatsAppMessageState
from langchain_openai import ChatOpenAI
import logging
import random
from datetime import datetime


def context_analysis_node(state: WhatsAppMessageState):
    """
    Analyze the order context and extract key information for message generation.
    """
    try:
        received_message = state.get("received_message", "")
        message_purpose = state.get("messagePurpose", "")

        # Parse the order data from the received message
        order_context = {}

        if message_purpose == "order_status_notification":
            # Try to extract structured data from the message
            try:
                # The received_message should contain the order data
                if "Customer Information:" in received_message:
                    lines = received_message.split("\n")

                    # Extract key information
                    for line in lines:
                        if "Name:" in line:
                            order_context["customer_name"] = line.split("Name:")[
                                -1
                            ].strip()
                        elif "Order #" in line:
                            order_context["order_number"] = (
                                line.split("Order #")[-1].split()[0].strip()
                            )
                        elif "Status:" in line:
                            order_context["status"] = line.split("Status:")[-1].strip()
                        elif "Total:" in line:
                            order_context["total"] = line.split("Total:")[-1].strip()

                # Determine urgency and emotion based on status
                status = order_context.get("status", "").lower()
                if "shipped" in status or "completed" in status:
                    order_context["emotion"] = "excited"
                    order_context["urgency"] = "medium"
                elif "cancelled" in status or "failed" in status:
                    order_context["emotion"] = "apologetic"
                    order_context["urgency"] = "high"
                elif "on-hold" in status or "pending" in status:
                    order_context["emotion"] = "reassuring"
                    order_context["urgency"] = "medium"
                else:
                    order_context["emotion"] = "neutral"
                    order_context["urgency"] = "low"

            except Exception as e:
                logging.warning(f"Could not parse order context: {e}")
                order_context = {
                    "customer_name": "valued customer",
                    "emotion": "neutral",
                    "urgency": "low",
                }

        return {**state, "order_context": order_context, "analysis_complete": True}

    except Exception as e:
        logging.error(f"Error in context_analysis_node: {e}")
        return {
            **state,
            "order_context": {"emotion": "neutral", "urgency": "low"},
            "analysis_complete": True,
        }


def tone_selection_node(state: WhatsAppMessageState):
    """
    Select appropriate tone and communication style based on context analysis.
    """
    try:
        order_context = state.get("order_context", {})
        emotion = order_context.get("emotion", "neutral")
        urgency = order_context.get("urgency", "low")

        # Define tone profiles
        tone_profiles = {
            "excited": {
                "greeting_style": "enthusiastic",
                "language_style": "celebratory",
                "emoji_usage": "moderate",
                "closing_style": "grateful",
            },
            "apologetic": {
                "greeting_style": "concerned",
                "language_style": "understanding",
                "emoji_usage": "minimal",
                "closing_style": "supportive",
            },
            "reassuring": {
                "greeting_style": "calm",
                "language_style": "informative",
                "emoji_usage": "light",
                "closing_style": "confident",
            },
            "neutral": {
                "greeting_style": "friendly",
                "language_style": "professional",
                "emoji_usage": "light",
                "closing_style": "standard",
            },
        }

        selected_tone = tone_profiles.get(emotion, tone_profiles["neutral"])

        # Add time-based greeting variation
        current_hour = datetime.now().hour
        if 5 <= current_hour < 12:
            time_greeting = "morning"
        elif 12 <= current_hour < 17:
            time_greeting = "afternoon"
        else:
            time_greeting = "evening"

        selected_tone["time_context"] = time_greeting

        return {**state, "selected_tone": selected_tone, "tone_selected": True}

    except Exception as e:
        logging.error(f"Error in tone_selection_node: {e}")
        return {
            **state,
            "selected_tone": {
                "greeting_style": "friendly",
                "language_style": "professional",
            },
            "tone_selected": True,
        }


def content_generation_node(state: WhatsAppMessageState):
    """
    Generate the core message content using LLM with specialized prompts.
    """
    try:
        config = state.get("configurable", {})
        model = config.get("model")

        if not model:
            model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.8)

        order_context = state.get("order_context", {})
        selected_tone = state.get("selected_tone", {})
        received_message = state.get("received_message", "")

        # Create specialized system prompt
        system_prompt = f"""You are an expert customer service representative crafting personalized WhatsApp messages.

TONE PROFILE:
- Greeting Style: {selected_tone.get("greeting_style", "friendly")}
- Language Style: {selected_tone.get("language_style", "professional")}
- Emotion Context: {order_context.get("emotion", "neutral")}
- Time Context: {selected_tone.get("time_context", "day")}

WRITING GUIDELINES:
1. Create a natural, conversational flow
2. Vary sentence structure and length
3. Use transitional phrases that feel human
4. Include specific details from the order
5. Avoid templated language patterns
6. Make it feel like a personal message from a real person
7. Keep it concise but warm (75-100 words)
8. Use natural language variations

STRUCTURE REQUIREMENTS:
- Personal greeting with name
- Clear status update with context
- Relevant next steps or information

Generate ONLY the message content. Do not include explanations or meta-commentary."""

        user_prompt = f"""Create a personalized WhatsApp message based on this order information:

{received_message}

Make this message feel genuinely personal and human, not like a template. Vary your language and approach."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = model.invoke(messages)
        generated_content = (
            response.content if hasattr(response, "content") else str(response)
        )

        return {
            **state,
            "generated_content": generated_content,
            "content_generated": True,
        }

    except Exception as e:
        logging.error(f"Error in content_generation_node: {e}")
        return {
            **state,
            "generated_content": "Thank you for your order. We'll keep you updated on its progress.",
            "content_generated": True,
        }


def personalization_node(state: WhatsAppMessageState):
    """
    Add personal touches and customization to the generated content.
    """
    try:
        generated_content = state.get("generated_content", "")
        order_context = state.get("order_context", {})
        selected_tone = state.get("selected_tone", {})

        # Add personalization elements
        personalized_content = generated_content

        # Add subtle variations based on tone
        emotion = order_context.get("emotion", "neutral")

        if emotion == "excited" and "shipped" in generated_content.lower():
            # Add excitement variations
            excitement_additions = [
                "\n\n🎉 We're as excited as you are!",
                "\n\nYour patience has paid off! 🌟",
                "\n\nAlmost there! 🚀",
            ]
            if random.random() < 0.3:  # 30% chance to add excitement
                personalized_content += random.choice(excitement_additions)

        elif emotion == "apologetic":
            # Add empathy
            if random.random() < 0.4:  # 40% chance for apologetic situations
                empathy_additions = [
                    "\n\nWe truly appreciate your patience.",
                    "\n\nThank you for understanding.",
                    "\n\nWe're here to help make this right.",
                ]
                personalized_content += random.choice(empathy_additions)

        return {
            **state,
            "personalized_content": personalized_content,
            "personalization_complete": True,
        }

    except Exception as e:
        logging.error(f"Error in personalization_node: {e}")
        return {
            **state,
            "personalized_content": state.get(
                "generated_content", "Thank you for your order."
            ),
            "personalization_complete": True,
        }


def formatting_node(state: WhatsAppMessageState):
    """
    Apply final formatting and structure to ensure proper WhatsApp presentation.
    """
    try:
        personalized_content = state.get("personalized_content", "")
        selected_tone = state.get("selected_tone", {})

        # Clean up formatting
        formatted_content = personalized_content.strip()

        # Ensure proper line breaks for WhatsApp
        formatted_content = formatted_content.replace("\n\n\n", "\n\n")

        # Add appropriate emoji usage based on tone
        emoji_usage = selected_tone.get("emoji_usage", "light")

        if emoji_usage == "minimal" and formatted_content.count("�") > 2:
            # Reduce emoji usage for apologetic messages
            import re

            emojis = re.findall(r"[🎉🌟🚀👋🙏🚚📅]", formatted_content)
            if len(emojis) > 2:
                # Keep only the first 2 emojis
                for emoji in emojis[2:]:
                    formatted_content = formatted_content.replace(emoji, "", 1)

        # Ensure message ends properly
        if not formatted_content.endswith(("!", ".", "🙏", "😊")):
            formatted_content += "!"

        return {
            **state,
            "final_message": formatted_content,
            "agent_response": formatted_content,
            "formatting_complete": True,
        }

    except Exception as e:
        logging.error(f"Error in formatting_node: {e}")
        return {
            **state,
            "final_message": state.get(
                "personalized_content", "Thank you for your order!"
            ),
            "agent_response": state.get(
                "personalized_content", "Thank you for your order!"
            ),
            "formatting_complete": True,
        }


def enhanced_agent_workflow_node(state: WhatsAppMessageState):
    """
    Orchestrate the multi-node workflow for enhanced message generation.
    """
    try:
        message_purpose = state.get("messagePurpose", "")

        if message_purpose == "order_status_notification":
            # Run through the enhanced workflow
            state = context_analysis_node(state)
            state = tone_selection_node(state)
            state = content_generation_node(state)
            state = personalization_node(state)
            state = formatting_node(state)

            return state
        else:
            # For non-order messages, use simplified approach
            return simplified_fallback_node(state)

    except Exception as e:
        logging.error(f"Error in enhanced_agent_workflow_node: {e}")
        return simplified_fallback_node(state)


def simplified_fallback_node(state: WhatsAppMessageState):
    """
    Fallback node for non-order messages or when the enhanced workflow fails.
    """
    try:
        config = state.get("configurable", {})
        model = config.get("model")

        if not model:
            model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)

        message_content = state.get("received_message", "No message content found.")

        system_prompt = """You are a helpful, friendly customer service assistant for an e-commerce store. 
        Respond naturally and helpfully to customer inquiries via WhatsApp. Keep responses concise and professional."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_content},
        ]

        response = model.invoke(messages)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        return {
            **state,
            "final_message": response_text,
            "agent_response": response_text,
        }

    except Exception as e:
        logging.error(f"Error in simplified_fallback_node: {e}")
        fallback_response = "Thank you for your message. We'll get back to you soon!"

        return {
            **state,
            "final_message": fallback_response,
            "agent_response": fallback_response,
        }


