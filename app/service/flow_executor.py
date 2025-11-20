"""
Flow execution service for processing flows triggered by incoming messages.
"""
from typing import Dict, Any, Optional, List
from app.models.flow import Flow


class FlowExecutor:
    """
    Executes flows based on their node configuration.
    This is a simple implementation that processes trigger and response nodes.
    """

    def __init__(self, flow: Flow):
        self.flow = flow
        self.nodes = {node["id"]: node for node in flow.nodes}
        self.edges = flow.edges

    def execute(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Execute the flow and return the response message.
        
        Args:
            context: Dictionary containing execution context (user_input, user_phone, etc.)
            
        Returns:
            Response message string or None
        """
        # Find the trigger node (entry point)
        trigger_node = self._find_trigger_node()
        if not trigger_node:
            print(f"No trigger node found in flow {self.flow.code}")
            return None

        # Start execution from trigger node
        current_node_id = trigger_node["id"]
        
        # Simple execution: follow edges to find response nodes
        visited = set()
        max_iterations = 20  # Prevent infinite loops
        iteration = 0
        
        while current_node_id and iteration < max_iterations:
            iteration += 1
            
            if current_node_id in visited:
                break
            visited.add(current_node_id)
            
            current_node = self.nodes.get(current_node_id)
            if not current_node:
                break
            
            # If we hit a response node, return its message
            if current_node["type"] == "response":
                return self._process_response_node(current_node, context)
            
            # Move to next node
            next_edges = [e for e in self.edges if e["source"] == current_node_id]
            if next_edges:
                current_node_id = next_edges[0]["target"]
            else:
                break
        
        return None

    def _find_trigger_node(self) -> Optional[Dict[str, Any]]:
        """Find the trigger node in the flow"""
        for node in self.flow.nodes:
            if node["type"] == "trigger":
                return node
        return None

    def _process_response_node(
        self, node: Dict[str, Any], context: Dict[str, Any]
    ) -> str:
        """
        Process a response node and return the message.
        Supports basic template variables.
        """
        data = node.get("data", {})
        message = data.get("message", "")
        
        # Simple template variable replacement
        # Replace {{variable}} with context values
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in message:
                message = message.replace(placeholder, str(value))
        
        return message


def execute_flow(flow: Flow, user_input: str, user_phone: str) -> Optional[str]:
    """
    Convenience function to execute a flow.
    
    Args:
        flow: The Flow model to execute
        user_input: The user's message text
        user_phone: The user's phone number
        
    Returns:
        Response message or None
    """
    executor = FlowExecutor(flow)
    context = {
        "user_input": user_input,
        "user_phone": user_phone,
        "message": user_input,
    }
    return executor.execute(context)
